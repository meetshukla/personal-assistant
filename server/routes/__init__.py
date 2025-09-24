"""API routes for Personal Assistant."""

from fastapi import APIRouter

from .chat import router as chat_router
from .gmail import router as gmail_router

api_router = APIRouter(prefix="/api")

api_router.include_router(chat_router)
api_router.include_router(gmail_router)

__all__ = ["api_router"]