from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.documents import router as documents_router

# initialize fastapi application
app = FastAPI(
  title = "Document Chatbot API",
  description = "A RAG-based chatbot for querying uploaded documents.",
  version = "1.0.0"
)

# configure CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins = ["*"],
  allow_credentials = True,
  allow_methods = ["*"],
  allow_headers = ["*"]
)

app.include_router(documents_router)

# root endpoint
@app.get("/")
def root():
  return {
    "message" : "Document Chatbot API is running!",
    "status" : "healthy"
  }