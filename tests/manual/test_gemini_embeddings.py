
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY is missing from .env")

client = genai.Client(api_key=api_key)

texts = [
    "RAG combines document retrieval with language model generation.",
    "Vector databases store embeddings for semantic similarity search.",
    "FastAPI is a Python framework for building APIs.",
]

# Each Content object represents one independent input.
contents = [
    types.Content(
        parts=[types.Part.from_text(text=text)]
    )
    for text in texts
]

response = client.models.embed_content(
    model="gemini-embedding-2",
    contents=contents,
    config=types.EmbedContentConfig(
        output_dimensionality=768,
    ),
)

embeddings = [
    embedding.values
    for embedding in response.embeddings
]

print("Embedding API test successful!")
print("Input texts:", len(texts))
print("Returned embeddings:", len(embeddings))
print("Embedding dimensions:", len(embeddings[0]))
print("First 5 values:", embeddings[0][:5])

assert len(embeddings) == len(texts)
assert all(len(vector) == 768 for vector in embeddings)

print("All assertions passed!")
