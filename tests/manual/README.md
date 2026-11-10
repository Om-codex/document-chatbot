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

The automated suite lives in `tests/` and uses temporary storage plus fakes.
