"""Cross-cutting error handling, health and logging tests."""

import logging

from app import app


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_endpoint(client, indexed_txt):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app_name"]
    assert payload["llm_model"]
    assert payload["embedding_model"]
    assert payload["collection"]
    assert payload["document_count"] == 1


def test_validation_errors_have_a_stable_shape(client):
    response = client.post("/api/chat/", json={"question": ""})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert isinstance(detail["details"], list)


def test_unexpected_route_errors_do_not_leak_internals(client, monkeypatch):
    from api.routes import documents as documents_route

    def broken_listing():
        raise RuntimeError("secret filesystem path C:\\private\\chroma.sqlite3")

    monkeypatch.setattr(documents_route, "list_documents", broken_listing)

    response = client.get("/api/documents/")

    assert response.status_code == 500
    body = response.text
    assert "secret filesystem" not in body
    assert "chroma.sqlite3" not in body
    assert "Traceback" not in body
    assert response.json()["detail"]["code"] == "INTERNAL_ERROR"


def test_global_exception_handler_returns_safe_json(client):
    @app.get("/_test/unhandled")
    def unhandled():
        raise RuntimeError("super secret implementation detail")

    response = client.get("/_test/unhandled")

    assert response.status_code == 500
    assert "super secret" not in response.text
    assert response.json()["detail"]["code"] == "INTERNAL_ERROR"


def test_logs_do_not_contain_api_key(client, upload_document, caplog):
    caplog.set_level(logging.INFO)

    upload_document("notes.txt", b"logging test content", "text/plain")
    client.post("/api/chat/", json={"question": "What is this about?"})

    assert "test-key" not in caplog.text
    assert "GROQ_API_KEY" not in caplog.text
