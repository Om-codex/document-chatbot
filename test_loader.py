from ingestion.loaders import load_document

file_path = "data/uploads/sample.pdf"

documents = load_document(file_path)

print("Total Documents: ",len(documents))

for i,doc in enumerate(documents):
  print(f"\nDocument {i+1}")
  print("Metadata: ",doc.metadata)
  print("Content: ",doc.page_content)


