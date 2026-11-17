# Manual scripts

These are the original exploratory scripts from the RAG milestones. They are
kept for reference but are **not** collected by pytest because they:

- run real embeddings and sometimes real Groq calls at import time;
- expect `data/uploads/sample.pdf` or two real PDFs;
- print output instead of asserting.

Run one explicitly from the project root, for example:

```powershell
.\.venv\Scripts\python.exe tests\manual\test_retriever.py
```

`test_qdrant_connection.py` and `test_gemini_embeddings.py` are live-service
smoke checks added during the Qdrant/Gemini migration. They read credentials
from `.env` and call the real APIs at import time, so they also belong here
rather than in the collected suite.

The automated suite lives in `tests/` and uses an in-memory vector store plus fakes.
