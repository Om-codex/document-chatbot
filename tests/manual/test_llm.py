from generation.llm import get_llm

llm = get_llm()

response = llm.invoke(
  "Explain what is RAG in short?"
)

print("LLM Response: \n", response.content)

# Display token usage
print("\nResponse Metadata:")
print(response.response_metadata)