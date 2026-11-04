from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

def get_llm():
  llm = ChatGroq(
    model = "openai/gpt-oss-20b",
    temperature = 0,
    max_retries = 2
  )

  return llm