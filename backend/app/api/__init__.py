"""API Routers Package."""
from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.collections import router as collections_router
from app.api.ingest import router as ingest_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(collections_router)
api_router.include_router(ingest_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
