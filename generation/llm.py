from functools import lru_cache

from langchain_groq import ChatGroq
from config.settings import settings

@lru_cache(maxsize = 1)
def get_llm():

    if settings.groq_api_key is None:
        raise ValueError("GROQ_API_KEY is not configured.")

    llm = ChatGroq(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        api_key=settings.groq_api_key.get_secret_value()
    )

    return llm
