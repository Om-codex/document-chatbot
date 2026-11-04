from ingestion.pipeline import ingest_document
from vectorstore.chroma_store import (
    add_documents,
    delete_documents,
    get_vector_store
)

chunks = ingest_document("data/uploads/sample.pdf")

doc_id = chunks[0].metadata["doc_id"]

add_documents(chunks)

delete_documents(doc_id)

vector_store = get_vector_store()

remaining = vector_store.get(
    where={"doc_id": doc_id}
)

print("Remaining chunks:", len(remaining["ids"]))