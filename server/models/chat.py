"""Chat and conversation models."""

from typing import List, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user", "assistant", "specialist"
    content: str
    timestamp: Optional[str] = None




class ChatHistoryResponse(BaseModel):
    """Response containing chat history."""
    messages: List[ChatMessage]


class ChatHistoryClearResponse(BaseModel):
    """Response for clearing chat history."""
    ok: bool = True
    message: str = "Chat history cleared successfully"