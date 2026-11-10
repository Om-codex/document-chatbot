
from pathlib import Path

from ingestion.pipeline import ingest_document
from vectorstore.chroma_store import (
    add_documents,
    get_all_documents,
    delete_documents
)
from retrieval.retriever import get_retriever
from chains.qa_chain import get_qa_chain


# --------------------------------------------------
# 1. Find two different PDF files
# --------------------------------------------------

upload_dir = Path("data/uploads")
pdf_files = sorted(upload_dir.glob("*.pdf"))

if len(pdf_files) < 2:
    raise RuntimeError(
        "Please add at least two different PDFs to data/uploads/"
    )

print("\n[1] Found PDF files:")
for file in pdf_files[:2]:
    print(f" - {file.name}")


# --------------------------------------------------
# 2. Ingest and store both documents
# --------------------------------------------------

ingested_documents = []

for file_path in pdf_files[:2]:
    chunks = ingest_document(str(file_path))

    if not chunks:
        raise RuntimeError(f"No chunks generated for {file_path.name}")

    doc_id = chunks[0].metadata["doc_id"]

    add_documents(chunks)

    ingested_documents.append({
        "filename": file_path.name,
        "doc_id": doc_id,
        "chunks": chunks
    })

    print(
        f"\nIngested: {file_path.name} "
        f"| Chunks: {len(chunks)}"
    )


first_doc = ingested_documents[0]
second_doc = ingested_documents[1]

if first_doc["doc_id"] == second_doc["doc_id"]:
    raise RuntimeError(
        "Both PDFs have identical content. Use two different PDFs."
    )


# --------------------------------------------------
# 3. Verify document listing
# --------------------------------------------------

print("\n[2] Indexed documents:")

indexed_documents = get_all_documents()

for document in indexed_documents:
    print(
        f"Filename: {document['filename']} "
        f"| Chunks: {document['total_chunks']}"
    )

indexed_ids = {
    document["doc_id"] for document in indexed_documents
}

assert first_doc["doc_id"] in indexed_ids
assert second_doc["doc_id"] in indexed_ids

print("PASS: Both documents are indexed.")


# --------------------------------------------------
# 4. Test retrieval across all documents
# --------------------------------------------------

print("\n[3] Testing retrieval across all documents...")

all_retriever = get_retriever(k=5)

all_results = all_retriever.invoke(
    "What are the main topics discussed in these documents?"
)

assert len(all_results) > 0

print(f"Retrieved {len(all_results)} chunks.")

for document in all_results:
    print({
        "filename": document.metadata.get("filename"),
        "doc_id": document.metadata.get("doc_id"),
        "chunk_index": document.metadata.get("chunk_index")
    })

print("PASS: Retrieval across all documents works.")


# --------------------------------------------------
# 5. Test document-specific retrieval
# --------------------------------------------------

print("\n[4] Testing selected-document retrieval...")

selected_retriever = get_retriever(
    k=5,
    doc_ids=[first_doc["doc_id"]]
)

selected_results = selected_retriever.invoke(
    "What are the main topics discussed in this document?"
)

assert len(selected_results) > 0

for document in selected_results:
    assert document.metadata["doc_id"] == first_doc["doc_id"]

print(f"Retrieved {len(selected_results)} chunks.")

print("PASS: Only the selected document was retrieved.")


# --------------------------------------------------
# 6. Test answer generation and source metadata
# --------------------------------------------------

print("\n[5] Testing QA chain...")

qa_chain = get_qa_chain(
    doc_ids=[first_doc["doc_id"]],
    k=3
)

question = "What is the main topic of this document?"

response = qa_chain.invoke(question)

assert response["answer"]
assert response["sources"]

print("\nAnswer:")
print(response["answer"])

print("\nSource documents:")

for source in response["sources"]:
    print({
        "filename": source.metadata.get("filename"),
        "page": source.metadata.get("page"),
        "chunk_index": source.metadata.get("chunk_index")
    })

print("PASS: Answer generation and source tracking work.")


# --------------------------------------------------
# 7. Test document deletion and restoration
# --------------------------------------------------

print("\n[6] Testing document deletion...")

second_doc_id = second_doc["doc_id"]

delete_documents(second_doc_id)

try:
    remaining_documents = get_all_documents()

    remaining_ids = {
        document["doc_id"] for document in remaining_documents
    }

    assert second_doc_id not in remaining_ids
    assert first_doc["doc_id"] in remaining_ids

    print("PASS: Selected document vectors were deleted.")
    print("PASS: Other document vectors remain intact.")

finally:
    # Restore the test document so the test doesn't
    # leave your vector database missing this document.
    add_documents(second_doc["chunks"])

restored_ids = {
    document["doc_id"]
    for document in get_all_documents()
}

assert second_doc_id in restored_ids

print("PASS: Deleted document was successfully restored.")


# --------------------------------------------------
# Final result
# --------------------------------------------------

print("\n" + "=" * 50)
print("ALL END-TO-END RAG TESTS PASSED!")
print("=" * 50)
