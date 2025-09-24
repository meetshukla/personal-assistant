"""Conversation memory management using Supabase."""

from datetime import datetime
from typing import List, Dict, Any, Optional
from functools import lru_cache

from ...models.chat import ChatMessage
from ...services.supabase_client import get_supabase_client
from ...logging_config import get_logger

logger = get_logger(__name__)


class ConversationMemory:
    """Manages conversation history with Supabase storage."""

    def __init__(self):
        self.client = get_supabase_client()

    async def record_user_message(self, phone_number: str, message: str, message_id: str = None) -> None:
        """Record a user message to the conversation history."""

        if not self.client:
            logger.warning("Cannot record message: Supabase client not available")
            return

        try:
            data = {
                "phone_number": phone_number,
                "role": "user",
                "content": message,
                "message_id": message_id,
                "timestamp": datetime.utcnow().isoformat()
            }

            result = self.client.table('conversations').insert(data).execute()
            logger.debug(f"Recorded user message from {phone_number}")

        except Exception as e:
            logger.error(f"Failed to record user message: {e}")

    async def record_assistant_message(self, phone_number: str, message: str) -> None:
        """Record an assistant response to the conversation history."""

        if not self.client:
            logger.warning("Cannot record message: Supabase client not available")
            return

        try:
            data = {
                "phone_number": phone_number,
                "role": "assistant",
                "content": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            result = self.client.table('conversations').insert(data).execute()
            logger.debug(f"Recorded assistant message to {phone_number}")

        except Exception as e:
            logger.error(f"Failed to record assistant message: {e}")

    async def record_specialist_message(self, phone_number: str, specialist_name: str, message: str) -> None:
        """Record a specialist message to the conversation history."""

        if not self.client:
            logger.warning("Cannot record message: Supabase client not available")
            return

        try:
            data = {
                "phone_number": phone_number,
                "role": "specialist",
                "content": f"[{specialist_name}] {message}",
                "timestamp": datetime.utcnow().isoformat()
            }

            result = self.client.table('conversations').insert(data).execute()
            logger.debug(f"Recorded specialist message from {specialist_name}")

        except Exception as e:
            logger.error(f"Failed to record specialist message: {e}")

    async def get_conversation_history(self, phone_number: str, limit: int = 100) -> List[ChatMessage]:
        """Get conversation history for a phone number."""

        if not self.client:
            logger.warning("Cannot get history: Supabase client not available")
            return []

        try:
            result = (
                self.client
                .table('conversations')
                .select('*')
                .eq('phone_number', phone_number)
                .order('timestamp', desc=False)
                .limit(limit)
                .execute()
            )

            messages = []
            for row in result.data:
                messages.append(ChatMessage(
                    role=row['role'],
                    content=row['content'],
                    timestamp=row['timestamp']
                ))

            logger.debug(f"Retrieved {len(messages)} messages for {phone_number}")
            return messages

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    async def get_conversation_transcript(self, phone_number: str, limit: int = 100) -> str:
        """Get conversation history as a formatted transcript."""

        messages = await self.get_conversation_history(phone_number, limit)

        if not messages:
            return ""

        transcript_lines = []
        for msg in messages:
            timestamp = msg.timestamp or ""
            if timestamp:
                timestamp = f" ({timestamp[:19]})"  # Keep YYYY-MM-DD HH:MM:SS format

            if msg.role == "user":
                transcript_lines.append(f"<user_message>{msg.content}</user_message>{timestamp}")
            elif msg.role == "assistant":
                transcript_lines.append(f"<conductor_reply>{msg.content}</conductor_reply>{timestamp}")
            elif msg.role == "specialist":
                transcript_lines.append(f"<specialist_message>{msg.content}</specialist_message>{timestamp}")

        return "\n".join(transcript_lines)

    async def clear_conversation(self, phone_number: str) -> None:
        """Clear conversation history for a phone number."""

        if not self.client:
            logger.warning("Cannot clear conversation: Supabase client not available")
            return

        try:
            result = (
                self.client
                .table('conversations')
                .delete()
                .eq('phone_number', phone_number)
                .execute()
            )

            logger.info(f"Cleared conversation history for {phone_number}")

        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")

    async def get_message_count(self, phone_number: str) -> int:
        """Get the number of messages in conversation history."""

        if not self.client:
            return 0

        try:
            result = (
                self.client
                .table('conversations')
                .select('id', count='exact')
                .eq('phone_number', phone_number)
                .execute()
            )

            return result.count or 0

        except Exception as e:
            logger.error(f"Failed to get message count: {e}")
            return 0


@lru_cache(maxsize=1)
def get_conversation_memory() -> ConversationMemory:
    """Get the global conversation memory instance."""
    return ConversationMemory()