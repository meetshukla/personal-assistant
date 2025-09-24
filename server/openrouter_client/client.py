"""OpenRouter API client for LLM requests."""

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx

from ..logging_config import get_logger

logger = get_logger(__name__)


async def request_chat_completion(
    model: str,
    messages: List[Dict[str, Any]],
    api_key: str,
    system: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Make a chat completion request to OpenRouter."""

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/personal-assistant",
        "X-Title": "Personal Assistant",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if system:
        # Add system message to the beginning
        payload["messages"] = [{"role": "system", "content": system}] + messages

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    if max_tokens:
        payload["max_tokens"] = max_tokens

    logger.debug(f"Making OpenRouter request to {model}")

    # Retry logic for rate limits
    max_retries = 3
    base_delay = 1

    for attempt in range(max_retries + 1):
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 429:  # Rate limit
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error("Rate limit exceeded, max retries reached")
                        response.raise_for_status()

                response.raise_for_status()
                result = response.json()
                logger.debug(f"OpenRouter response received")
                return result

            except httpx.HTTPError as e:
                if attempt == max_retries:
                    logger.error(f"OpenRouter API error after {max_retries + 1} attempts: {e}")
                    raise
                else:
                    logger.warning(f"Request failed (attempt {attempt + 1}), retrying: {e}")
                    await asyncio.sleep(base_delay)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenRouter response: {e}")
                raise