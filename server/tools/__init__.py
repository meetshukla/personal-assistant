"""Pure Tool Functions - No LLM logic, just focused functionality."""

from . import llm_tool
from . import scheduler_tool

# Import gmail_tool - should work now with fixed client
try:
    from . import gmail_tool
    _gmail_available = True
except Exception as e:
    gmail_tool = None
    _gmail_available = False
    import logging
    logging.getLogger(__name__).warning(f"Gmail tools not available: {e}")

from .registry import ToolRegistry

__all__ = ["llm_tool", "scheduler_tool", "ToolRegistry"]
if _gmail_available:
    __all__.append("gmail_tool")