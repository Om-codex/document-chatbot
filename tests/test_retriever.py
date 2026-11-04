from retrieval.retriever import get_retriever

# initialize retriever
retriever = get_retriever(k = 3)

# ask question
query = "What is the main topic of this document?"

# retrieve the relevant chunks
results = retriever.invoke(query)

print("Retrieved chunks: ",len(results))

for i, doc in enumerate(results):
  print(f"\n--- Retrieved Chunk {i + 1}")
  print("Content:\n",doc.page_content[:500])
  print("Metadata:\n",doc.metadata)