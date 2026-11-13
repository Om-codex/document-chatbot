import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes.chat import router as chat_router
from api.routes.documents import router as documents_router
from api.routes.health import router as health_router
from config.settings import settings
from utils.logging_config import configure_logging

configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info(
        "Configuration loaded: llm_model=%s embedding_model=%s collection=%s",
        settings.llm_model,
        settings.gemini_embedding_model,
        settings.qdrant_collection_name,
    )

    if settings.groq_api_key is None:
        logger.warning(
            "GROQ_API_KEY is not configured. Chat requests will fail until it is set."
        )

    yield

    logger.info("Shutting down %s", settings.app_name)


# initialize fastapi application
app = FastAPI(
    title=settings.app_name,
    description="A RAG-based chatbot for querying uploaded documents.",
    version=settings.app_version,
    lifespan=lifespan,
)

# configure CORS (needed only when the frontend is served from another origin)
allow_all_origins = "*" in settings.cors_allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    """Return one predictable validation shape instead of leaking internals."""

    errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": "The request body or parameters are invalid.",
                "details": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    """Last-resort handler: log the traceback server-side, return a safe message."""

    logger.exception("Unhandled application error.", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred.",
            }
        },
    )


app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(health_router)


# root endpoint
@app.get("/")
def root():
    return {
        "message": "Document Chatbot API is running!",
        "status": "healthy",
        "docs": "/docs",
        "ui": "/app",
    }


# Serve the static frontend from the same origin. This must be mounted last:
# Starlette matches routes in declaration order.
if settings.frontend_directory.is_dir():
    app.mount(
        "/app",
        StaticFiles(directory=str(settings.frontend_directory), html=True),
        name="frontend",
    )
