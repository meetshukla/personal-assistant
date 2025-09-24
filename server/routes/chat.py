"""Chat routes for web interface."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

from ..models.chat import ChatMessage, ChatHistoryResponse
from ..conductor.runtime import MessageConductorRuntime
from ..services.conversation import get_conversation_memory
from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: str = "web_user"


class ChatResponse(BaseModel):
    """Chat response model."""
    message: str
    success: bool
    specialists_used: int = 0


@router.post("/send", response_model=ChatResponse)
async def send_message(request: ChatRequest) -> ChatResponse:
    """Send a message to the assistant and get a response."""

    try:
        logger.info(f"🌐 WEB API: Received message from {request.session_id}: '{request.message}'")

        runtime = MessageConductorRuntime()
        result = await runtime.execute(request.message, request.session_id)

        logger.info(f"🌐 WEB API: Returning response (success: {result.success}, workers: {result.workers_used}, specialists: {result.specialists_used})")

        return ChatResponse(
            message=result.response,
            success=result.success,
            specialists_used=result.specialists_used
        )

    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str = "web_user") -> ChatHistoryResponse:
    """Get chat history for a session."""

    try:
        memory = get_conversation_memory()
        messages = await memory.get_conversation_history(session_id, limit=100)

        return ChatHistoryResponse(messages=messages)

    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/history")
async def clear_chat_history(session_id: str = "web_user") -> JSONResponse:
    """Clear chat history for a session."""

    try:
        memory = get_conversation_memory()
        await memory.clear_conversation(session_id)

        return JSONResponse({"ok": True, "message": "Chat history cleared"})

    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/notifications")
async def get_new_notifications(session_id: str = "web_user", since_timestamp: Optional[str] = None) -> ChatHistoryResponse:
    """Get new notifications (messages) since the given timestamp."""

    try:
        memory = get_conversation_memory()

        # Get recent messages
        messages = await memory.get_conversation_history(session_id, limit=50)

        # Filter messages since timestamp if provided
        if since_timestamp:
            try:
                from datetime import datetime
                # Fix common timestamp format issues
                normalized_timestamp = since_timestamp.replace('Z', '+00:00')
                # Fix space before timezone to + sign
                if ' 00:00' in normalized_timestamp:
                    normalized_timestamp = normalized_timestamp.replace(' 00:00', '+00:00')

                since_dt = datetime.fromisoformat(normalized_timestamp)
                logger.debug(f"Parsed since_timestamp: {since_dt}")

                # Convert message timestamps to datetime objects for comparison
                filtered_messages = []
                for msg in messages:
                    try:
                        if isinstance(msg.timestamp, str):
                            msg_timestamp = msg.timestamp.replace('Z', '+00:00')
                            # Fix space before timezone to + sign for message timestamps too
                            if ' 00:00' in msg_timestamp:
                                msg_timestamp = msg_timestamp.replace(' 00:00', '+00:00')
                            msg_dt = datetime.fromisoformat(msg_timestamp)
                        else:
                            msg_dt = msg.timestamp

                        if msg_dt > since_dt:
                            filtered_messages.append(msg)
                    except Exception as parse_error:
                        logger.debug(f"Failed to parse message timestamp {msg.timestamp}: {parse_error}")
                        # If timestamp parsing fails, include the message to be safe
                        filtered_messages.append(msg)

                messages = filtered_messages
                logger.debug(f"Filtered to {len(messages)} messages since {since_dt}")
            except Exception as e:
                logger.warning(f"Invalid timestamp format: {since_timestamp}, error: {e}")

        return ChatHistoryResponse(messages=messages)

    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


__all__ = ["router"]