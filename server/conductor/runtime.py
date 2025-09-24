"""Message Conductor Runtime - handles LLM calls for user and specialist turns."""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .message_conductor import build_conductor_system_prompt, prepare_conductor_message_with_history
from .tools import ToolResult, get_conductor_tool_schemas, handle_conductor_tool_call
from ..config import get_settings
from ..openrouter_client import request_chat_completion
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ConductorResult:
    """Result from the Message Conductor."""

    success: bool
    response: str
    error: Optional[str] = None
    specialists_used: int = 0
    workers_used: int = 0  # Track workers used for new architecture


@dataclass
class _ToolCall:
    """Parsed tool invocation from an LLM response."""

    identifier: Optional[str]
    name: str
    arguments: Dict[str, Any]


@dataclass
class _LoopSummary:
    """Aggregate information produced by the conductor loop."""

    last_assistant_text: str = ""
    user_messages: List[str] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    specialists: Set[str] = field(default_factory=set)
    workers_executed: int = 0  # Track worker executions


class MessageConductorRuntime:
    """Manages the Message Conductor's request processing."""

    MAX_TOOL_ITERATIONS = 8

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openrouter_api_key
        self.model = settings.message_conductor_model
        self.settings = settings
        self.tool_schemas = get_conductor_tool_schemas()

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable."
            )

    async def execute(self, user_message: str, from_number: str) -> ConductorResult:
        """Handle a user-authored message from the web interface."""

        try:
            logger.info(f"🎯 NEW USER MESSAGE: '{user_message}' from {from_number}")

            from ..services.conversation import get_conversation_memory
            from ..services.conversation.summarization import ConversationSummarizer

            memory = get_conversation_memory()

            # Record user message
            await memory.record_user_message(from_number, user_message)

            # Get conversation history
            conversation_history = await memory.get_conversation_transcript(from_number)

            # Check if we should summarize
            summarizer = ConversationSummarizer()
            if await summarizer.should_summarize_conversation(from_number, memory):
                await summarizer.summarize_conversation(from_number, memory)
                # Reload conversation history after summarization
                conversation_history = await memory.get_conversation_transcript(from_number)

            system_prompt = build_conductor_system_prompt()
            messages = prepare_conductor_message_with_history(
                user_message, conversation_history, message_type="user"
            )

            logger.info("🤖 Starting Message Conductor processing loop...")
            summary = await self._run_conductor_loop(system_prompt, messages, from_number)

            final_response = self._finalize_response(summary)

            logger.info(f"✅ Conductor processing complete. Workers used: {summary.workers_executed}, Specialists used: {len(summary.specialists)}")

            # Record assistant response
            if final_response:
                await memory.record_assistant_message(from_number, final_response)
                logger.info(f"💾 Saved assistant response to conversation history")

            return ConductorResult(
                success=True,
                response=final_response,
                specialists_used=len(summary.specialists),
                workers_used=summary.workers_executed,
            )

        except Exception as exc:
            logger.error("Message Conductor failed", extra={"error": str(exc)})
            return ConductorResult(
                success=False,
                response="",
                error=str(exc),
            )

    async def handle_specialist_message(self, specialist_message: str, from_number: str) -> ConductorResult:
        """Process a status update emitted by a Service Specialist."""

        try:
            # TODO: Load conversation history from database
            conversation_history = ""

            system_prompt = build_conductor_system_prompt()
            messages = prepare_conductor_message_with_history(
                specialist_message, conversation_history, message_type="specialist"
            )

            logger.info("Processing Service Specialist results")
            summary = await self._run_conductor_loop(system_prompt, messages, from_number)

            final_response = self._finalize_response(summary)

            # TODO: Save conversation to database

            return ConductorResult(
                success=True,
                response=final_response,
                specialists_used=len(summary.specialists),
                workers_used=summary.workers_executed,
            )

        except Exception as exc:
            logger.error("Message Conductor (specialist message) failed", extra={"error": str(exc)})
            return ConductorResult(
                success=False,
                response="",
                error=str(exc),
            )

    async def _run_conductor_loop(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        from_number: str
    ) -> _LoopSummary:
        """Iteratively query the LLM until it issues a final response."""

        summary = _LoopSummary()

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            try:
                response = await asyncio.wait_for(
                    self._make_llm_call(system_prompt, messages),
                    timeout=20.0  # 20 second timeout for LLM calls
                )
                assistant_message = self._extract_assistant_message(response)
            except asyncio.TimeoutError:
                logger.error(f"LLM call timed out on iteration {iteration}")
                # Return a simple fallback response
                summary.last_assistant_text = "I'm sorry, I'm having trouble processing your request right now. Please try again."
                break

            assistant_content = (assistant_message.get("content") or "").strip()
            if assistant_content:
                summary.last_assistant_text = assistant_content

            raw_tool_calls = assistant_message.get("tool_calls") or []
            parsed_tool_calls = self._parse_tool_calls(raw_tool_calls)

            assistant_entry: Dict[str, Any] = {
                "role": "assistant",
                "content": assistant_message.get("content", "") or "",
            }
            if raw_tool_calls:
                assistant_entry["tool_calls"] = raw_tool_calls
            messages.append(assistant_entry)

            if not parsed_tool_calls:
                break

            for tool_call in parsed_tool_calls:
                summary.tool_names.append(tool_call.name)

                if tool_call.name in ["plan_and_execute_task", "schedule_task_for_later"]:
                    # Track new architecture usage
                    summary.workers_executed += 1
                    logger.info(f"🚀 NEW ARCHITECTURE: Using {tool_call.name} - Worker execution #{summary.workers_executed}")

                # Add timeout to prevent hanging
                try:
                    # Different timeouts based on tool complexity
                    timeout_seconds = 120.0  # 2 minute default timeout
                    if tool_call.name in ["plan_and_execute_task"]:
                        timeout_seconds = 180.0  # 3 minutes for complex operations

                    logger.info(f"🔧 TOOL: Executing {tool_call.name} with {timeout_seconds}s timeout")
                    result = await asyncio.wait_for(
                        self._execute_tool(tool_call, from_number),
                        timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Tool execution timed out: {tool_call.name}")
                    result = ToolResult(
                        success=False,
                        response="⚠️ Tool execution timed out. Please try again.",
                        user_message=None
                    )

                if result.user_message:
                    summary.user_messages.append(result.user_message)

                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.identifier or tool_call.name,
                    "content": self._format_tool_result(tool_call, result),
                }
                messages.append(tool_message)
        else:
            raise RuntimeError("Reached tool iteration limit without final response")

        if not summary.user_messages and not summary.last_assistant_text:
            logger.warning("Conductor loop exited without assistant content")

        return summary

    async def _make_llm_call(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Make an LLM call via OpenRouter."""

        logger.debug(
            "Message Conductor calling LLM",
            extra={"model": self.model, "tools": len(self.tool_schemas)},
        )
        return await request_chat_completion(
            model=self.model,
            messages=messages,
            system=system_prompt,
            api_key=self.api_key,
            tools=self.tool_schemas,
        )

    def _extract_assistant_message(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Return the assistant message from the raw response payload."""

        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("LLM response did not include an assistant message")
        return message

    def _parse_tool_calls(self, raw_tool_calls: List[Dict[str, Any]]) -> List[_ToolCall]:
        """Normalize tool call payloads from the LLM."""

        parsed: List[_ToolCall] = []
        for raw in raw_tool_calls:
            function_block = raw.get("function") or {}
            name = function_block.get("name")
            if not isinstance(name, str) or not name:
                logger.warning("Skipping tool call without name", extra={"tool": raw})
                continue

            arguments, error = self._parse_tool_arguments(function_block.get("arguments"))
            if error:
                logger.warning("Tool call arguments invalid", extra={"tool": name, "error": error})
                parsed.append(
                    _ToolCall(
                        identifier=raw.get("id"),
                        name=name,
                        arguments={"__invalid_arguments__": error},
                    )
                )
                continue

            parsed.append(
                _ToolCall(identifier=raw.get("id"), name=name, arguments=arguments)
            )

        return parsed

    def _parse_tool_arguments(
        self, raw_arguments: Any
    ) -> tuple[Dict[str, Any], Optional[str]]:
        """Convert tool arguments into a dictionary, reporting errors."""

        if raw_arguments is None:
            return {}, None

        if isinstance(raw_arguments, dict):
            return raw_arguments, None

        if isinstance(raw_arguments, str):
            if not raw_arguments.strip():
                return {}, None
            try:
                parsed = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                return {}, f"invalid json: {exc}"
            if isinstance(parsed, dict):
                return parsed, None
            return {}, "decoded arguments were not an object"

        return {}, f"unsupported argument type: {type(raw_arguments).__name__}"

    async def _execute_tool(self, tool_call: _ToolCall, from_number: str) -> ToolResult:
        """Execute a tool call and convert low-level errors into structured results."""

        if "__invalid_arguments__" in tool_call.arguments:
            error = tool_call.arguments["__invalid_arguments__"]
            self._log_tool_invocation(tool_call, stage="rejected", detail={"error": error})
            return ToolResult(success=False, payload={"error": error})

        try:
            self._log_tool_invocation(tool_call, stage="start")

            # Add session context for web tools
            if tool_call.name == "send_notification" and "session_id" not in tool_call.arguments:
                tool_call.arguments["session_id"] = from_number

            result = await handle_conductor_tool_call(tool_call.name, tool_call.arguments)
        except Exception as exc:
            logger.error(
                "Tool execution crashed",
                extra={"tool": tool_call.name, "error": str(exc)},
            )
            self._log_tool_invocation(
                tool_call,
                stage="error",
                detail={"error": str(exc)},
            )
            return ToolResult(success=False, payload={"error": str(exc)})

        if not isinstance(result, ToolResult):
            logger.warning(
                "Tool did not return ToolResult; coercing",
                extra={"tool": tool_call.name},
            )
            wrapped = ToolResult(success=True, payload=result)
            self._log_tool_invocation(tool_call, stage="done", result=wrapped)
            return wrapped

        status = "success" if result.success else "error"
        logger.debug(
            "Tool executed",
            extra={
                "tool": tool_call.name,
                "status": status,
            },
        )
        self._log_tool_invocation(tool_call, stage="done", result=result)
        return result

    def _format_tool_result(self, tool_call: _ToolCall, result: ToolResult) -> str:
        """Render a tool execution result back to the LLM."""

        payload: Dict[str, Any] = {
            "tool": tool_call.name,
            "status": "success" if result.success else "error",
            "arguments": {
                key: value
                for key, value in tool_call.arguments.items()
                if key != "__invalid_arguments__"
            },
        }

        if result.payload is not None:
            key = "result" if result.success else "error"
            payload[key] = result.payload

        return self._safe_json_dump(payload)

    def _safe_json_dump(self, payload: Any) -> str:
        """Serialize payload to JSON, falling back to repr on failure."""

        try:
            return json.dumps(payload, default=str)
        except TypeError:
            return repr(payload)

    def _log_tool_invocation(
        self,
        tool_call: _ToolCall,
        *,
        stage: str,
        result: Optional[ToolResult] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit structured logs for tool lifecycle events."""

        cleaned_args = {
            key: value
            for key, value in tool_call.arguments.items()
            if key != "__invalid_arguments__"
        }

        log_payload: Dict[str, Any] = {
            "tool": tool_call.name,
            "stage": stage,
            "arguments": cleaned_args,
        }

        if result is not None:
            log_payload["success"] = result.success
            if result.payload is not None:
                log_payload["payload"] = result.payload

        if detail:
            log_payload.update(detail)

        if stage == "done":
            logger.info(f"Tool '{tool_call.name}' completed")
        elif stage in {"error", "rejected"}:
            logger.warning(f"Tool '{tool_call.name}' {stage}")
        else:
            logger.debug(f"Tool '{tool_call.name}' {stage}")

    def _finalize_response(self, summary: _LoopSummary) -> str:
        """Decide what text should be exposed to the user as the final reply."""

        if summary.user_messages:
            return summary.user_messages[-1]

        return summary.last_assistant_text

    async def execute_planner_worker_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute a task using the new Planner -> Worker architecture."""

        try:
            from ..planner import TaskPlanner
            from ..workers import TaskWorker

            # Initialize components
            planner = TaskPlanner()
            worker = TaskWorker()

            # Create execution plan
            logger.info(f"Creating plan for task: {task_description}")
            plan = await planner.create_plan(task_description, context)

            # Execute plan
            logger.info(f"Executing plan {plan.plan_id} with {len(plan.steps)} steps")
            result = await worker.execute_plan(plan, context)

            if result.success:
                logger.info(f"Successfully completed task: {task_description}")
                return result.final_result
            else:
                logger.error(f"Task execution failed: {result.error}")
                return f"❌ **Task Failed**\n\n{result.error}\n\nSteps completed: {result.steps_executed}/{len(plan.steps)}"

        except Exception as e:
            logger.error(f"Planner-Worker execution failed: {e}")
            return f"❌ **System Error**\n\nFailed to execute task: {str(e)}"

    def _detect_task_complexity(self, task_description: str) -> str:
        """Detect if a task should use new architecture or old specialists."""

        task_lower = task_description.lower()

        # Keywords that suggest complex multi-step tasks
        complex_keywords = [
            "summarize", "analyze", "check", "search", "fetch", "get", "find",
            "send", "create", "update", "delete", "list", "compare", "review",
            "remind", "schedule", "in", "minutes", "hours", "days", "at", "tomorrow"
        ]

        # Time-based scheduling patterns
        time_patterns = [
            r"\bin\s+\d+\s*(minutes?|mins?|hours?|hrs?|days?)",
            r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)?",
            r"\btomorrow\b",
            r"\bnext\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"\d{1,2}:\d{2}",
        ]

        # Check for scheduling patterns
        for pattern in time_patterns:
            if re.search(pattern, task_description):
                return "schedule"

        # Check for complex task keywords
        complex_count = sum(1 for keyword in complex_keywords if keyword in task_lower)

        if complex_count >= 2:
            return "complex"
        elif complex_count >= 1:
            return "simple_complex"
        else:
            return "simple"

    def _should_use_new_architecture(self, task_description: str) -> bool:
        """Determine if task should use new Planner-Worker architecture."""

        complexity = self._detect_task_complexity(task_description)

        # Use new architecture for complex and scheduled tasks
        return complexity in ["complex", "schedule", "simple_complex"]