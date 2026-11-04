from ingestion.text_splitter import split_documents
from ingestion.loaders import load_document

file_path = "data/uploads/sample.pdf"

documents = load_document(file_path)

print("Original documents: ",len(documents))

chunks = split_documents(documents, chunk_size=1000, chunk_overlap=200)
print("Total chunks: ", len(chunks))

for i, chunk in enumerate(chunks[:5]):

    print(f"\n--- Chunk {i + 1} ---")

    print("Metadata:", chunk.metadata)

    print("Content:", chunk.page_content[:300])

    print("Chunk length:", len(chunk.page_content))