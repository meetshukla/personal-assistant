"""Tools available to the Message Conductor."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger
# Removed WhatsApp dependency - now using web interface

logger = get_logger(__name__)


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    payload: Any
    user_message: Optional[str] = None


def get_conductor_tool_schemas() -> List[Dict[str, Any]]:
    """Get tool schemas for the Message Conductor."""
    return [
        {
            "type": "function",
            "function": {
                "name": "plan_and_execute_task",
                "description": "Execute a complex task using the new Planner-Worker architecture. Best for multi-step tasks involving emails, analysis, or data processing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "Clear description of the task to execute (e.g., 'Summarize my emails from today', 'Check recent emails and draft responses')"
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context information for the task",
                            "properties": {
                                "user_id": {"type": "string", "description": "User identifier"},
                                "priority": {"type": "string", "description": "Task priority level"}
                            }
                        }
                    },
                    "required": ["task_description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "schedule_task_for_later",
                "description": "Schedule a task for future execution. Use when user specifies a delay (e.g., 'in 5 minutes', 'at 3pm', 'tomorrow').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "Description of the task to schedule"
                        },
                        "delay_minutes": {
                            "type": "integer",
                            "description": "How many minutes from now to execute the task"
                        },
                        "execution_time": {
                            "type": "string",
                            "description": "Specific execution time in ISO format (alternative to delay_minutes)"
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context for the scheduled task"
                        }
                    },
                    "required": ["task_description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_message_to_user",
                "description": "Send a message to the user via web interface.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to send to the user."
                        }
                    },
                    "required": ["message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_draft",
                "description": "Display an email draft to the user for review.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address."
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line."
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content."
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "wait",
                "description": "Wait and avoid sending duplicate responses to the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Reason for waiting (what duplication is being avoided)."
                        }
                    },
                    "required": ["reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_notification",
                "description": "Send a notification message to the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Notification message to send."
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high"],
                            "description": "Priority level of the notification."
                        }
                    },
                    "required": ["message"]
                }
            }
        }
    ]


async def handle_conductor_tool_call(tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
    """Handle tool calls for the Message Conductor."""

    try:
        if tool_name == "plan_and_execute_task":
            return await _handle_plan_and_execute_task(arguments)
        elif tool_name == "schedule_task_for_later":
            return await _handle_schedule_task_for_later(arguments)
        elif tool_name == "send_message_to_user":
            return await _handle_send_message_to_user(arguments)
        elif tool_name == "send_draft":
            return _handle_send_draft(arguments)
        elif tool_name == "wait":
            return _handle_wait(arguments)
        elif tool_name == "send_notification":
            return await _handle_send_notification(arguments)
        else:
            return ToolResult(success=False, payload={"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return ToolResult(success=False, payload={"error": str(e)})



async def _handle_send_message_to_user(arguments: Dict[str, Any]) -> ToolResult:
    """Handle sending a message to the user."""
    message = arguments.get("message", "")

    # This creates a user message that will be sent via web interface
    return ToolResult(
        success=True,
        payload={"message": message},
        user_message=message
    )


def _handle_send_draft(arguments: Dict[str, Any]) -> ToolResult:
    """Handle displaying an email draft."""
    to = arguments.get("to", "")
    subject = arguments.get("subject", "")
    body = arguments.get("body", "")

    draft_text = f"📧 **Email Draft**\n\n**To:** {to}\n**Subject:** {subject}\n\n**Body:**\n{body}"

    return ToolResult(
        success=True,
        payload={"to": to, "subject": subject, "body": body},
        user_message=draft_text
    )


def _handle_wait(arguments: Dict[str, Any]) -> ToolResult:
    """Handle wait instruction."""
    reason = arguments.get("reason", "")

    logger.info(f"Wait instruction: {reason}")

    return ToolResult(
        success=True,
        payload={"reason": reason, "action": "wait"}
    )


async def _handle_send_notification(arguments: Dict[str, Any]) -> ToolResult:
    """Handle sending notification message."""
    message = arguments.get("message", "")
    priority = arguments.get("priority", "normal")

    # For web interface, notifications are handled differently
    # They could be stored and shown in the UI, or sent via other means
    logger.info(f"Notification ({priority}): {message}")

    return ToolResult(
        success=True,
        payload={"message": message, "priority": priority, "sent": True}
    )


async def _handle_plan_and_execute_task(arguments: Dict[str, Any]) -> ToolResult:
    """Handle executing a task using the new Planner-Worker architecture."""

    task_description = arguments.get("task_description", "")
    context = arguments.get("context", {})

    if not task_description:
        return ToolResult(
            success=False,
            payload={"error": "Task description is required"}
        )

    try:
        from ..planner import TaskPlanner
        from ..workers import TaskWorker

        # Initialize components
        planner = TaskPlanner()
        worker = TaskWorker()

        # Add default user_id if not provided
        if "user_id" not in context:
            context["user_id"] = "web_user"

        # Create and execute plan
        logger.info(f"📋 PLANNER: Creating execution plan for task: '{task_description}'")
        plan = await planner.create_plan(task_description, context)
        logger.info(f"📋 PLANNER: Plan created with {len(plan.steps)} steps - ID: {plan.plan_id}")

        logger.info(f"⚙️ WORKER: Starting plan execution...")
        result = await worker.execute_plan(plan, context)
        logger.info(f"⚙️ WORKER: Execution {'✅ COMPLETED' if result.success else '❌ FAILED'} - {result.steps_executed}/{len(plan.steps)} steps")

        if result.success:
            return ToolResult(
                success=True,
                payload={
                    "task": task_description,
                    "plan_id": plan.plan_id,
                    "steps_executed": result.steps_executed,
                    "result": result.final_result
                },
                user_message=result.final_result
            )
        else:
            return ToolResult(
                success=False,
                payload={
                    "task": task_description,
                    "error": result.error,
                    "steps_executed": result.steps_executed
                },
                user_message=f"❌ **Task Failed**: {result.error}"
            )

    except Exception as e:
        logger.error(f"Failed to execute planned task: {e}")
        return ToolResult(
            success=False,
            payload={"error": str(e)},
            user_message=f"❌ **System Error**: {str(e)}"
        )


async def _handle_schedule_task_for_later(arguments: Dict[str, Any]) -> ToolResult:
    """Handle scheduling a task for future execution."""

    task_description = arguments.get("task_description", "")
    delay_minutes = arguments.get("delay_minutes")
    execution_time = arguments.get("execution_time")
    context = arguments.get("context", {})

    if not task_description:
        return ToolResult(
            success=False,
            payload={"error": "Task description is required"}
        )

    try:
        from ..tools.scheduler_tool import schedule_task, store_complex_task
        from datetime import datetime, timedelta

        # Add default user_id if not provided
        user_id = context.get("user_id", "web_user")

        if delay_minutes:
            # Schedule with delay
            logger.info(f"⏰ SCHEDULER: Scheduling task for {delay_minutes} minutes from now")
            result = await schedule_task(task_description, delay_minutes, user_id, context)
        elif execution_time:
            # Schedule for specific time
            logger.info(f"⏰ SCHEDULER: Scheduling task for specific time: {execution_time}")
            result = await store_complex_task(task_description, execution_time, user_id, None)
        else:
            # Default to 1 minute delay
            logger.info(f"⏰ SCHEDULER: No time specified, defaulting to 1 minute delay")
            result = await schedule_task(task_description, 1, user_id, context)

        if result.get("success"):
            scheduled_time = result.get("scheduled_time") or result.get("execution_time")
            message = f"✅ **Task Scheduled**\n\n📝 **Task**: {task_description}\n⏰ **Scheduled for**: {scheduled_time}\n🔢 **ID**: {result.get('task_id', 'N/A')}"

            return ToolResult(
                success=True,
                payload=result,
                user_message=message
            )
        else:
            return ToolResult(
                success=False,
                payload={"error": "Failed to schedule task"},
                user_message="❌ **Scheduling Failed**: Could not schedule task"
            )

    except Exception as e:
        logger.error(f"Failed to schedule task: {e}")
        return ToolResult(
            success=False,
            payload={"error": str(e)},
            user_message=f"❌ **Scheduling Error**: {str(e)}"
        )