from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from config.settings import settings

@lru_cache(maxsize = 1)
def get_embedding_model():
  embedding_model = HuggingFaceEmbeddings(
    model_name = settings.embedding_model_name,
    model_kwargs = {
      "device": settings.embedding_device
    },
    encode_kwargs = {
      "normalize_embeddings": settings.normalize_embeddings
    }
  )

  return embedding_model