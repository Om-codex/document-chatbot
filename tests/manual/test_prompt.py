from chains.prompt_template import get_rag_prompt

prompt = get_rag_prompt()

context = """
Supervised learning is a machine learning technique
where models learn from labeled training data.
"""

question = "What is supervised learning?"

formatted_prompt = prompt.invoke({
  "context":context,
  "question":question
})

for message in formatted_prompt.messages:

    print(f"\nRole: {message.type}")

    print("Content:")

    print(message.content)
