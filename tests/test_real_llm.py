"""Optional real-provider smoke test.

Run only when you explicitly want to spend a Groq request:

    $env:RUN_REAL_LLM_TESTS = "1"
    .\.venv\Scripts\python.exe -m pytest tests\test_real_llm.py -v -m real_api

The test uses a temporary Chroma collection and uploads a tiny TXT document.
"""

import os

import pytest
from fastapi.testclient import TestClient

from config.settings import settings

pytestmark = [
    pytest.mark.real_api,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_LLM_TESTS") != "1",
        reason="Set RUN_REAL_LLM_TESTS=1 to run the real Groq smoke test.",
    ),
]


@pytest.fixture
def real_client(isolated_storage):
    """Like the normal client fixture, but without the fake LLM patch."""

    from app import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.skipif(
    settings.groq_api_key is None,
    reason="GROQ_API_KEY is not configured.",
)
def test_real_groq_chat(real_client):
    upload = real_client.post(
        "/api/documents/upload",
        files={
            "file": (
                "smoke.txt",
                b"Caching stores frequently used data close to the application.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200, upload.text

    response = real_client.post(
        "/api/chat/",
        json={"question": "What does the document say about caching?", "k": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answer"]
    assert payload["total_chunks_retrieved"] >= 1
