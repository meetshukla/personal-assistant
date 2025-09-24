"""Message Conductor agent for handling user conversations."""

from typing import List, Dict, Any

from .tools import get_conductor_tool_schemas
from ..logging_config import get_logger

logger = get_logger(__name__)


def build_conductor_system_prompt() -> str:
    """Build the system prompt for the Message Conductor."""

    try:
        from pathlib import Path
        prompt_path = Path(__file__).parent / "system_prompt.md"

        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            logger.warning("System prompt file not found, using fallback")
            return _get_fallback_system_prompt()

    except Exception as e:
        logger.error(f"Error loading system prompt: {e}")
        return _get_fallback_system_prompt()


def _get_fallback_system_prompt() -> str:
    """Fallback system prompt if file cannot be loaded."""
    return """You are a Personal Assistant Message Conductor that helps users via web interface with email management and reminders.

You can execute complex tasks using the Planner-Worker architecture:
- Use plan_and_execute_task for email operations, analysis, reminders
- Use schedule_task_for_later for future execution
- Always inform users before starting complex tasks

IMPORTANT: **Always format your responses using Markdown** to make them visually appealing:
- Use **bold** for important information
- Use bullet points for lists
- Use `code blocks` for technical terms
- Use headers (##) to organize information

Always be helpful and well-formatted in your responses. Use the available tools to execute tasks and communicate results back to the user."""


def prepare_conductor_message_with_history(
    user_message: str,
    conversation_history: str,
    message_type: str = "user"
) -> List[Dict[str, Any]]:
    """Prepare messages for the Message Conductor with conversation history."""

    messages = []

    # Add conversation history if available
    if conversation_history.strip():
        messages.append({
            "role": "user",
            "content": f"<conversation_history>\n{conversation_history}\n</conversation_history>"
        })

    # Add the current message (only support user messages now)
    content = f"<new_user_message>\n{user_message}\n</new_user_message>"

    messages.append({
        "role": "user",
        "content": content
    })

    return messages