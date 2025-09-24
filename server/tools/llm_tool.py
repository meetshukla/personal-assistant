"""LLM Tool Functions - Pure LLM utility functions via OpenRouter."""

from typing import Any, Dict, List

from ..config import get_settings
from ..openrouter_client import request_chat_completion
from ..logging_config import get_logger

logger = get_logger(__name__)


async def summarize(text: str, max_length: int = 200) -> str:
    """Summarize text using LLM."""

    try:
        settings = get_settings()

        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key not configured")

        system_prompt = f"""You are a text summarizer. Create a clear, concise summary of the provided text.

Requirements:
- Maximum length: {max_length} characters
- Capture key points and important information
- Use clear, readable language
- Format with markdown if helpful for readability"""

        messages = [{"role": "user", "content": f"Please summarize this text:\n\n{text}"}]

        response = await request_chat_completion(
            model=settings.specialist_model,
            messages=messages,
            system=system_prompt,
            api_key=settings.openrouter_api_key,
            tools=[]
        )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("Empty response from LLM")

        # Truncate if too long
        if len(content) > max_length:
            content = content[:max_length-3] + "..."

        logger.info(f"Generated summary of {len(text)} characters -> {len(content)} characters")
        return content

    except Exception as e:
        logger.error(f"Failed to summarize text: {e}")
        raise RuntimeError(f"Text summarization failed: {str(e)}")


async def analyze(text: str, task: str) -> str:
    """Analyze text for a specific task using LLM."""

    try:
        settings = get_settings()

        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key not configured")

        system_prompt = f"""You are a text analyzer. Analyze the provided text according to the specific task requested.

Task: {task}

Provide a clear, helpful analysis that directly addresses the task. Use markdown formatting for better readability."""

        messages = [{"role": "user", "content": f"Please analyze this text:\n\n{text}"}]

        response = await request_chat_completion(
            model=settings.specialist_model,
            messages=messages,
            system=system_prompt,
            api_key=settings.openrouter_api_key,
            tools=[]
        )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("Empty response from LLM")

        logger.info(f"Analyzed text for task: {task}")
        return content

    except Exception as e:
        logger.error(f"Failed to analyze text: {e}")
        raise RuntimeError(f"Text analysis failed: {str(e)}")


async def classify(text: str, categories: List[str]) -> Dict[str, Any]:
    """Classify text into provided categories using LLM."""

    try:
        settings = get_settings()

        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key not configured")

        categories_str = ", ".join(categories)

        system_prompt = f"""You are a text classifier. Classify the provided text into one of these categories: {categories_str}

Respond with JSON in this format:
{{
  "category": "selected_category",
  "confidence": 0.95,
  "reasoning": "brief explanation"
}}

The category must be exactly one of the provided options."""

        messages = [{"role": "user", "content": f"Please classify this text:\n\n{text}"}]

        response = await request_chat_completion(
            model=settings.specialist_model,
            messages=messages,
            system=system_prompt,
            api_key=settings.openrouter_api_key,
            tools=[]
        )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("Empty response from LLM")

        # Try to parse JSON response
        import json
        try:
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)

                # Validate result
                if "category" in result and result["category"] in categories:
                    logger.info(f"Classified text as: {result['category']}")
                    return result
                else:
                    raise ValueError("Invalid category in response")
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            # Fallback: try to find category in response text
            for category in categories:
                if category.lower() in content.lower():
                    return {
                        "category": category,
                        "confidence": 0.5,
                        "reasoning": "Fallback classification based on keyword match"
                    }

            # Ultimate fallback
            return {
                "category": categories[0] if categories else "unknown",
                "confidence": 0.1,
                "reasoning": "Classification failed, using default category"
            }

    except Exception as e:
        logger.error(f"Failed to classify text: {e}")
        raise RuntimeError(f"Text classification failed: {str(e)}")


async def extract_information(text: str, fields: List[str]) -> Dict[str, str]:
    """Extract specific information fields from text using LLM."""

    try:
        settings = get_settings()

        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key not configured")

        fields_str = ", ".join(fields)

        system_prompt = f"""You are an information extractor. Extract the following fields from the provided text: {fields_str}

Respond with JSON in this format:
{{
  "field1": "extracted_value_or_not_found",
  "field2": "extracted_value_or_not_found"
}}

If a field cannot be found, use "not_found" as the value."""

        messages = [{"role": "user", "content": f"Please extract information from this text:\n\n{text}"}]

        response = await request_chat_completion(
            model=settings.specialist_model,
            messages=messages,
            system=system_prompt,
            api_key=settings.openrouter_api_key,
            tools=[]
        )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("Empty response from LLM")

        # Try to parse JSON response
        import json
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)

                logger.info(f"Extracted {len(result)} fields from text")
                return result
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse extraction JSON: {e}")
            # Fallback: return not_found for all fields
            return {field: "not_found" for field in fields}

    except Exception as e:
        logger.error(f"Failed to extract information: {e}")
        raise RuntimeError(f"Information extraction failed: {str(e)}")


async def generate_response(prompt: str, context: str = "") -> str:
    """Generate a response to a prompt using LLM."""

    try:
        settings = get_settings()

        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key not configured")

        system_prompt = """You are a helpful assistant. Provide a clear, useful response to the user's prompt.

Use markdown formatting for better readability when appropriate."""

        user_message = prompt
        if context:
            user_message = f"Context: {context}\n\nRequest: {prompt}"

        messages = [{"role": "user", "content": user_message}]

        response = await request_chat_completion(
            model=settings.specialist_model,
            messages=messages,
            system=system_prompt,
            api_key=settings.openrouter_api_key,
            tools=[]
        )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("Empty response from LLM")

        logger.info(f"Generated response for prompt: {prompt[:50]}...")
        return content

    except Exception as e:
        logger.error(f"Failed to generate response: {e}")
        raise RuntimeError(f"Response generation failed: {str(e)}")


# Tool function registry for discovery
LLM_TOOLS = {
    "summarize": summarize,
    "analyze": analyze,
    "classify": classify,
    "extract_information": extract_information,
    "generate_response": generate_response,
}