"""Tool Registry - Discovery and execution of all available tools."""

import inspect
from typing import Any, Callable, Dict, List, Optional

from ..logging_config import get_logger
from . import gmail_tool
from . import llm_tool
from . import scheduler_tool

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for discovering and executing tools."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_metadata: Dict[str, Dict[str, Any]] = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize all available tools."""

        # Register Gmail tools if available
        try:
            logger.info("🔄 Attempting to register Gmail tools...")
            from . import gmail_tool
            logger.info(f"📧 Gmail tool module imported: {gmail_tool}")

            if gmail_tool and hasattr(gmail_tool, 'GMAIL_TOOLS'):
                gmail_tools = gmail_tool.GMAIL_TOOLS
                logger.info(f"📧 Found GMAIL_TOOLS with {len(gmail_tools)} tools: {list(gmail_tools.keys())}")

                for name, func in gmail_tools.items():
                    full_name = f"gmail_tool.{name}"
                    logger.info(f"📧 Registering Gmail tool: {full_name}")
                    self._tools[full_name] = func
                    self._tool_metadata[full_name] = self._extract_metadata(func, "gmail")
                    logger.info(f"✅ Gmail tool registered: {full_name}")

                logger.info(f"✅ Gmail tools registered successfully: {len(gmail_tools)} tools")
            else:
                logger.warning("❌ Gmail tools module available but GMAIL_TOOLS not found")
                logger.info(f"📧 gmail_tool attributes: {dir(gmail_tool) if gmail_tool else 'None'}")
        except Exception as e:
            logger.error(f"❌ Gmail tools not available: {e}")
            logger.exception("Gmail tools registration exception:")

        # Register LLM tools
        for name, func in llm_tool.LLM_TOOLS.items():
            full_name = f"llm_tool.{name}"
            self._tools[full_name] = func
            self._tool_metadata[full_name] = self._extract_metadata(func, "llm")

        # Register Scheduler tools
        for name, func in scheduler_tool.SCHEDULER_TOOLS.items():
            full_name = f"scheduler_tool.{name}"
            self._tools[full_name] = func
            self._tool_metadata[full_name] = self._extract_metadata(func, "scheduler")

        logger.info(f"Initialized tool registry with {len(self._tools)} tools")

    def _extract_metadata(self, func: Callable, category: str) -> Dict[str, Any]:
        """Extract metadata from a function."""

        signature = inspect.signature(func)
        parameters = {}

        for param_name, param in signature.parameters.items():
            # Handle type annotation safely
            type_name = "Any"
            if param.annotation != inspect.Parameter.empty:
                try:
                    type_name = param.annotation.__name__
                except AttributeError:
                    # Handle complex types like List[str], Dict[str, Any], etc.
                    type_name = str(param.annotation)

            param_info = {
                "type": type_name,
                "required": param.default == inspect.Parameter.empty,
                "default": param.default if param.default != inspect.Parameter.empty else None
            }
            parameters[param_name] = param_info

        # Handle return type annotation safely
        return_type = "Any"
        if signature.return_annotation != inspect.Signature.empty:
            try:
                return_type = signature.return_annotation.__name__
            except AttributeError:
                return_type = str(signature.return_annotation)

        return {
            "category": category,
            "description": func.__doc__ or f"Execute {func.__name__}",
            "parameters": parameters,
            "return_type": return_type
        }

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool function with the given arguments."""

        logger.info(f"🔧 TOOL CALL: {tool_name}")
        logger.info(f"📝 Tool args: {args}")

        if tool_name not in self._tools:
            available_tools = list(self._tools.keys())
            logger.error(f"❌ Tool '{tool_name}' not found")
            logger.info(f"📋 Available tools: {available_tools}")
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {available_tools}")

        func = self._tools[tool_name]
        logger.info(f"✅ Found tool function: {func}")

        try:
            logger.info(f"🔧 TOOL: Calling {tool_name} with args: {list(args.keys())}")

            # Validate arguments against function signature
            signature = inspect.signature(func)
            logger.info(f"📝 Function signature: {signature}")

            bound_args = signature.bind(**args)
            bound_args.apply_defaults()
            logger.info(f"✅ Arguments bound successfully: {bound_args.arguments}")

            # Call the function
            if inspect.iscoroutinefunction(func):
                logger.info(f"🔄 Calling async function {tool_name}...")
                result = await func(**bound_args.arguments)
            else:
                logger.info(f"🔄 Calling sync function {tool_name}...")
                result = func(**bound_args.arguments)

            logger.info(f"🔧 TOOL: ✅ {tool_name} completed successfully")
            logger.info(f"📊 Tool result type: {type(result)}")
            logger.info(f"📊 Tool result: {result}")
            return result

        except TypeError as e:
            logger.error(f"❌ Invalid arguments for tool {tool_name}: {e}")
            logger.exception("Argument validation error:")
            raise ValueError(f"Invalid arguments for tool {tool_name}: {str(e)}")
        except Exception as e:
            logger.error(f"🔧 TOOL: ❌ {tool_name} execution failed: {e}")
            logger.exception("Tool execution error:")
            raise RuntimeError(f"Tool {tool_name} execution failed: {str(e)}")

    def get_available_tools(self) -> List[str]:
        """Get list of all available tools."""
        return list(self._tools.keys())

    def get_tools_by_category(self, category: str) -> List[str]:
        """Get tools filtered by category."""
        return [
            tool_name for tool_name, metadata in self._tool_metadata.items()
            if metadata.get("category") == category
        ]

    def get_tool_metadata(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific tool."""
        return self._tool_metadata.get(tool_name)

    def get_all_tool_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all tools."""
        return self._tool_metadata.copy()

    def search_tools(self, query: str) -> List[str]:
        """Search for tools by name or description."""
        query_lower = query.lower()
        matching_tools = []

        for tool_name, metadata in self._tool_metadata.items():
            if (query_lower in tool_name.lower() or
                query_lower in metadata.get("description", "").lower()):
                matching_tools.append(tool_name)

        return matching_tools

    def validate_tool_args(self, tool_name: str, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments for a tool without executing it."""

        if tool_name not in self._tools:
            return False, f"Tool '{tool_name}' not found"

        func = self._tools[tool_name]

        try:
            signature = inspect.signature(func)
            bound_args = signature.bind(**args)
            bound_args.apply_defaults()
            return True, None
        except TypeError as e:
            return False, str(e)

    def get_tool_categories(self) -> List[str]:
        """Get list of all tool categories."""
        categories = set()
        for metadata in self._tool_metadata.values():
            categories.add(metadata.get("category", "unknown"))
        return list(categories)

    def get_tool_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics for tools (placeholder for future implementation)."""
        # This could be enhanced to track actual usage statistics
        return {
            "total_tools": len(self._tools),
            "categories": {category: len(self.get_tools_by_category(category))
                         for category in self.get_tool_categories()},
            "tools_by_category": {
                category: self.get_tools_by_category(category)
                for category in self.get_tool_categories()
            }
        }

    def generate_tool_documentation(self) -> str:
        """Generate documentation for all available tools."""

        doc = "# Available Tools\n\n"

        for category in sorted(self.get_tool_categories()):
            doc += f"## {category.title()} Tools\n\n"

            tools_in_category = self.get_tools_by_category(category)
            for tool_name in sorted(tools_in_category):
                metadata = self._tool_metadata[tool_name]
                doc += f"### {tool_name}\n\n"
                doc += f"{metadata.get('description', 'No description available')}\n\n"

                if metadata.get('parameters'):
                    doc += "**Parameters:**\n"
                    for param_name, param_info in metadata['parameters'].items():
                        required = " (required)" if param_info['required'] else f" (optional, default: {param_info['default']})"
                        doc += f"- `{param_name}`: {param_info['type']}{required}\n"
                    doc += "\n"

                doc += f"**Returns:** {metadata.get('return_type', 'Any')}\n\n"
                doc += "---\n\n"

        return doc