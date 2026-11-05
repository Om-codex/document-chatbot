
from ingestion.pipeline import ingest_document

from vectorstore.chroma_store import (
    add_documents,
    get_all_documents,
    delete_documents,
    get_vector_store
)


# Ingest multiple documents
file_paths = [
    "data/uploads/sample.pdf","data/uploads/sample1.pdf"
]

for file_path in file_paths:

    chunks = ingest_document(file_path)

    ids = add_documents(chunks)

    print(f"\nIngested: {file_path}")
    print("Chunks stored:", len(ids))


# List all documents
print("\n========== DOCUMENT LIST ==========")

documents = get_all_documents()

for document in documents:
    print(document)


# Test duplicate prevention
print("\n========== DUPLICATE TEST ==========")

chunks = ingest_document(file_paths[0])

add_documents(chunks)

documents_after = get_all_documents()

print("Documents before/after:", len(documents), len(documents_after))


# Test deletion
print("\n========== DELETION TEST ==========")

doc_id = chunks[0].metadata["doc_id"]

delete_documents(doc_id)

vector_store = get_vector_store()

remaining = vector_store.get(
    where={"doc_id": doc_id}
)

print("Remaining chunks:", len(remaining["ids"]))
