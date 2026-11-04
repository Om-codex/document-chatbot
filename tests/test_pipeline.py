from ingestion.pipeline import ingest_document

file_path = "data/uploads/sample.pdf"

chunks = ingest_document(file_path)

print("Total chunks generated:", len(chunks))

for i, chunk in enumerate(chunks[:5]):

    print(f"\n--- Chunk {i + 1} ---")

    print("Metadata:", chunk.metadata)

    print("Content:", chunk.page_content[:300])

    print("Length:", len(chunk.page_content))