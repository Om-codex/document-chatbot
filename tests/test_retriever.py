from retrieval.retriever import get_retriever
from vector_store.chroma_store import get_all_documents

# step 1: list available documents
documents = get_all_documents()

print("Available Documents:")
for document in documents:
  print(document)

if not documents:
  raise RuntimeError("No documents found in ChromaDB")

# step 2: Search across all documents
print("\n========== All Documents ===========")

retriever = get_retriever(k = 3)

results = retriever.invoke(
  "What is the main topic of this document?"
)

for i, doc in enumerate(results):
  print(f"\nResult {i + 1}")
  print("Filename:", doc.metadata.get("filename"))
  print("Page:", doc.metadata.get("page"))
  print("Content:", doc.page_content[:200])


# step 3: search within the first document

selected_doc_id = documents[0]["doc_id"]

print("\n============ Selected Document =============")

retriever = get_retriever(
  k = 3,
  doc_ids = [selected_doc_id]
)

results = retriever.invoke(
  "What is the main topic of this document?"
)

for i, doc in enumerate(results):
  print(f"\nResult {i + 1}")
  print("Filename:", doc.metadata.get("filename"))
  print("Page:", doc.metadata.get("page"))
  print("Content:", doc.page_content[:200])

# step 4: Verify filtering
assert all(
  doc.metadata["doc_id"] == selected_doc_id for doc in results
)

print("\nDocument filtering test passed!")