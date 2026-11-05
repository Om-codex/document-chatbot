from chains.qa_chain import get_qa_chain
from vectorstore.chroma_store import get_all_documents


# Get indexed documents
documents = get_all_documents()

if not documents:
    raise RuntimeError("No documents found. Ingest a document first.")

print("\nAvailable documents:")

for document in documents:
    print(
        f"Filename: {document['filename']} | "
        f"ID: {document['doc_id']}"
    )


# Select the first document
selected_doc_id = documents[0]["doc_id"]

# Build QA chain for that document only
qa_chain = get_qa_chain(
    doc_ids=[selected_doc_id],
    k=3
)

# Ask a question
question = "What is the main topic of this document?"

result = qa_chain.invoke(question)

print("\nAnswer:")
print(result["answer"])

print("\nSources:")

for source in result["sources"]:
    print({
        "filename": source.metadata.get("filename"),
        "page": source.metadata.get("page"),
        "chunk_index": source.metadata.get("chunk_index")
    })
