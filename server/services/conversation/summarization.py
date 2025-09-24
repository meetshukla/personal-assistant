"""Conversation summarization for memory management."""

from typing import List, Optional
from datetime import datetime

from ...config import get_settings
from ...openrouter_client import request_chat_completion
from ...logging_config import get_logger
from .memory import ConversationMemory

logger = get_logger(__name__)


class ConversationSummarizer:
    """Handles conversation summarization to manage memory efficiently."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.openrouter_api_key
        self.model = self.settings.summarizer_model

    async def should_summarize_conversation(self, phone_number: str, memory: ConversationMemory) -> bool:
        """Check if conversation should be summarized based on message count."""

        if not self.settings.summarization_enabled:
            return False

        message_count = await memory.get_message_count(phone_number)
        return message_count >= self.settings.conversation_summary_threshold

    async def summarize_conversation(self, phone_number: str, memory: ConversationMemory) -> Optional[str]:
        """Summarize conversation history for a phone number."""

        if not self.api_key:
            logger.warning("Cannot summarize: OpenRouter API key not configured")
            return None

        try:
            # Get full conversation history
            transcript = await memory.get_conversation_transcript(phone_number)

            if not transcript.strip():
                return None

            # Generate summary using LLM
            summary = await self._generate_summary(transcript, phone_number)

            if summary:
                # Store summary and optionally clear old messages
                await self._store_summary(phone_number, summary, memory)

            return summary

        except Exception as e:
            logger.error(f"Failed to summarize conversation for {phone_number}: {e}")
            return None

    async def _generate_summary(self, transcript: str, phone_number: str) -> Optional[str]:
        """Generate conversation summary using LLM."""

        system_prompt = """You are a conversation summarizer for a personal assistant.

Your task is to create a comprehensive summary of the conversation that preserves:
1. Important context about the user's preferences and patterns
2. Active tasks, reminders, and ongoing projects
3. Key relationships and contacts mentioned
4. Email threads and important communications
5. Scheduling patterns and regular commitments

Create a structured summary that maintains temporal context. Use this format:

## User Profile & Preferences
[Key information about the user's communication style, preferences, timezone, etc.]

## Active Tasks & Reminders
[Current reminders, scheduled tasks, ongoing projects]

## Email Context
[Important email threads, contacts, patterns]

## Relationship Context
[Important people, their roles, communication patterns]

## Recent Interactions Summary
[Chronological summary of recent important interactions]

Be comprehensive but concise. Focus on information that will help the assistant provide better service in future interactions."""

        messages = [
            {
                "role": "user",
                "content": f"Please summarize this conversation with user {phone_number}:\n\n{transcript}"
            }
        ]

        try:
            response = await request_chat_completion(
                model=self.model,
                messages=messages,
                system=system_prompt,
                api_key=self.api_key,
                temperature=0.3  # Lower temperature for more consistent summaries
            )

            assistant_message = response.get("choices", [{}])[0].get("message", {})
            summary = assistant_message.get("content", "").strip()

            if summary:
                logger.info(f"Generated conversation summary for {phone_number}")
                return summary

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")

        return None

    async def _store_summary(self, phone_number: str, summary: str, memory: ConversationMemory) -> None:
        """Store conversation summary and manage old messages."""

        try:
            # For now, we'll store the summary as a special message
            # In a more advanced implementation, we might have a separate summaries table
            summary_message = f"CONVERSATION_SUMMARY:\n{summary}\n\nGenerated at: {datetime.utcnow().isoformat()}"

            await memory.record_specialist_message(
                phone_number,
                "ConversationSummarizer",
                summary_message
            )

            # Optionally: Clear older messages, keeping only recent ones
            # This would require implementing a more sophisticated cleanup strategy

            logger.info(f"Stored conversation summary for {phone_number}")

        except Exception as e:
            logger.error(f"Failed to store summary: {e}")

    async def get_latest_summary(self, phone_number: str, memory: ConversationMemory) -> Optional[str]:
        """Get the most recent conversation summary."""

        try:
            messages = await memory.get_conversation_history(phone_number, limit=50)

            # Look for the most recent summary message
            for message in reversed(messages):
                if (message.role == "specialist" and
                    message.content.startswith("[ConversationSummarizer] CONVERSATION_SUMMARY:")):

                    # Extract just the summary content
                    content = message.content
                    if "CONVERSATION_SUMMARY:\n" in content:
                        summary_start = content.find("CONVERSATION_SUMMARY:\n") + len("CONVERSATION_SUMMARY:\n")
                        summary_end = content.find("\n\nGenerated at:")
                        if summary_end > summary_start:
                            return content[summary_start:summary_end].strip()

            return None

        except Exception as e:
            logger.error(f"Failed to get latest summary: {e}")
            return None