"""
Weave PDF/CSV RAG Application Entrypoint.

Production-grade multi-tenant Retrieval-Augmented Generation (RAG) system:
- Ingestion pipelines for PDFs (PyMuPDF + Tesseract OCR fallback (planned)) and CSVs (dynamic typed PostgreSQL tables + semantic vector embeddings).
- 384-dimensional dense vector embeddings with pgvector HNSW indexing.
- Query router directing qualitative questions to Hybrid Semantic RAG and numeric calculations to live SQL aggregation on PostgreSQL.
- Dual-provider LLM failover (Google Gemini with automatic Groq fallback on quota exhaustion).
- Mechanically-attached deterministic citations with zero hallucination.
- Real-time Server-Sent Events (SSE) streaming for ingestion progress and token-by-token chat responses.
"""


from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.database import db
from app.db.schema import init_schema

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager handling database connection and schema initialization."""
    
    await db.connect()
    
    try:
        await init_schema()
    except Exception as e:
        logger.warning(f"Schema initialization deferred or failed: {e}")

    # pre-run embedding model in background thread
    import asyncio
    from app.services.embedding import embedding_service
    app.state.embedding_load_task = asyncio.create_task(
        asyncio.to_thread(embedding_service.load_model)
    )

    # everything before "yield" runs when the server starts up
    yield

    # everything after "yield" runs when the server shuts down
    await db.disconnect()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Production-quality RAG system over PDFs and CSVs with "
        "deterministic citations, SQL aggregation routing, and multi-tenant collections."
    ),
    lifespan=lifespan,
)

# cors middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include all api routes (both root and /api prefixes for client/proxy compatibility)
app.include_router(api_router)
app.include_router(api_router, prefix="/api")

# root endpoint
@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Root endpoint providing service status."""
    return {
        "service": settings.app_name,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }
