from ingestion.pipeline import ingest_document

from vectorstore.chroma_store import (add_documents, get_vector_store)

file_path = "data/uploads/sample.pdf"

# ingest the document and get chunks
chunks = ingest_document(file_path)
print("Chunks generated: ", len(chunks))

# store the chunks in ChromaDB
ids = add_documents(chunks)
print("Chunks stored: ", len(ids))

# retrieve the similar documents (semantic context)
vector_store = get_vector_store()

results = vector_store.similarity_search(
  "What is the main topic of this document?",
  k = 3
)

# results 
print("\nRetrieved documents:", len(results))

for i, doc in enumerate(results):

    print(f"\n--- Result {i + 1} ---")

    print("Content:", doc.page_content[:300])

    print("Metadata:", doc.metadata)
