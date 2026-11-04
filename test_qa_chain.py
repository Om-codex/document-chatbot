
from chains.qa_chain import get_qa_chain


qa_chain = get_qa_chain()

question = "What is the main topic of this document?"

response = qa_chain.invoke(question)


# Display answer
print("\nQUESTION:")
print(question)

print("\nANSWER:")
print(response["answer"])


# Display sources
print("\nSOURCES:")

for i, source in enumerate(response["sources"]):

    print(f"\nSource {i + 1}")

    print("Filename:", source.metadata.get("filename"))

    print("Page:", source.metadata.get("page"))

    print("Chunk:", source.metadata.get("chunk_index"))

    print("Content:", source.page_content[:200])
