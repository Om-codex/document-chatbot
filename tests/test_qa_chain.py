
from chains.qa_chain import get_qa_chain


# Initialize RAG chain
qa_chain = get_qa_chain()


# Ask a question
question = "What is the main topic of this document?"


# Generate answer
response = qa_chain.invoke(question)


print("\nUser Question:")
print(question)

print("\nRAG Response:")
print(response)
