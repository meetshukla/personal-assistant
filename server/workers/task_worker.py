"""Task Worker - LLM-powered executor that follows plans and calls tools."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..openrouter_client import request_chat_completion
from ..logging_config import get_logger
from ..planner.planner import ExecutionPlan, PlanStep

logger = get_logger(__name__)


@dataclass
class WorkerResult:
    """Result from worker execution."""

    success: bool
    final_result: str
    steps_executed: int
    execution_log: List[Dict[str, Any]]
    error: Optional[str] = None


@dataclass
class StepResult:
    """Result from executing a single step."""

    success: bool
    result: Any
    error: Optional[str] = None
    retry_count: int = 0


class TaskWorker:
    """LLM-powered task executor that follows plans intelligently."""

    MAX_RETRIES = 3
    MAX_EXECUTION_STEPS = 20

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openrouter_api_key
        self.model = settings.specialist_model  # Use specialist model for execution

        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        # Import tool registry here to avoid circular imports
        from ..tools.registry import ToolRegistry
        self.tool_registry = ToolRegistry()

    async def execute_plan(self, plan: ExecutionPlan, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """Execute the given plan step by step with LLM oversight."""

        execution_log = []
        step_results = {}

        try:
            logger.info(f"⚙️ WORKER: Starting execution of plan: {plan.plan_id}")
            logger.info(f"⚙️ WORKER: Plan has {len(plan.steps)} steps to execute")

            # Initialize context
            if context is None:
                context = {}
            context["user_id"] = context.get("user_id", "web_user")

            # Execute each step
            for i, step in enumerate(plan.steps):
                if i >= self.MAX_EXECUTION_STEPS:
                    raise RuntimeError(f"Exceeded maximum execution steps ({self.MAX_EXECUTION_STEPS})")

                logger.info(f"⚙️ WORKER: 🔄 Executing step {i+1}/{len(plan.steps)}: {step.step_id}")
                logger.info(f"⚙️ WORKER: Tool: {step.tool}")
                logger.info(f"⚙️ WORKER: Description: {step.description}")

                # Resolve arguments with previous step results
                resolved_args = self._resolve_step_arguments(step.args, step_results, context)

                # Execute the step with retries
                step_result = await self._execute_step_with_retries(step, resolved_args)

                # Log the step execution
                log_entry = {
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "args": resolved_args,
                    "success": step_result.success,
                    "retry_count": step_result.retry_count
                }

                if step_result.success:
                    log_entry["result"] = step_result.result
                    step_results[f"step_{step.step_id}_result"] = step_result.result
                    logger.info(f"⚙️ WORKER: ✅ Step {i+1} completed successfully")
                else:
                    log_entry["error"] = step_result.error
                    logger.error(f"⚙️ WORKER: ❌ Step {i+1} failed: {step_result.error}")
                    # Decide whether to continue or abort using LLM
                    should_continue = await self._should_continue_after_error(
                        plan, step, step_result.error, step_results, i
                    )
                    if not should_continue:
                        logger.warning(f"⚙️ WORKER: 🛑 Aborting execution after step {i+1} failure")
                        execution_log.append(log_entry)
                        # Generate helpful error message for Gmail connection issues
                        if "Gmail not connected" in step_result.error or "No connected account found" in step_result.error:
                            error_message = f"📧 **Gmail Connection Required**\n\nI tried to {step.description.lower()}, but your Gmail account isn't connected yet.\n\n**To connect Gmail:**\n1. Use the Gmail settings in the interface\n2. Follow the connection process\n3. Try your request again\n\n*Task: {plan.task_description}*"
                        else:
                            error_message = f"❌ **Task Failed**\n\n{step_result.error}\n\nSteps completed: {i + 1}/{len(plan.steps)}"

                        return WorkerResult(
                            success=False,
                            final_result=error_message,
                            steps_executed=i + 1,
                            execution_log=execution_log,
                            error=step_result.error
                        )

                execution_log.append(log_entry)

            # Generate final result using LLM
            logger.info(f"⚙️ WORKER: 📝 Generating final result summary...")
            final_result = await self._generate_final_result(plan, step_results, execution_log)

            logger.info(f"⚙️ WORKER: 🎉 Successfully completed execution of plan: {plan.plan_id}")
            logger.info(f"⚙️ WORKER: Executed {len(plan.steps)} steps successfully")

            return WorkerResult(
                success=True,
                final_result=final_result,
                steps_executed=len(plan.steps),
                execution_log=execution_log
            )

        except Exception as e:
            logger.error(f"Failed to execute plan {plan.plan_id}: {e}")
            return WorkerResult(
                success=False,
                final_result=f"Execution failed: {str(e)}",
                steps_executed=len(execution_log),
                execution_log=execution_log,
                error=str(e)
            )

    async def _execute_step_with_retries(self, step: PlanStep, args: Dict[str, Any]) -> StepResult:
        """Execute a single step with retry logic."""

        for attempt in range(self.MAX_RETRIES):
            try:
                # Call the tool function
                result = await self.tool_registry.call_tool(step.tool, args)

                return StepResult(
                    success=True,
                    result=result,
                    retry_count=attempt
                )

            except Exception as e:
                logger.warning(f"Step {step.step_id} failed on attempt {attempt + 1}: {e}")

                if attempt == self.MAX_RETRIES - 1:
                    # Last attempt failed
                    return StepResult(
                        success=False,
                        result=None,
                        error=str(e),
                        retry_count=attempt + 1
                    )

                # For retries, we could use LLM to modify arguments
                # For now, just retry with same arguments

        # This should never be reached, but just in case
        return StepResult(
            success=False,
            result=None,
            error="Maximum retries exceeded",
            retry_count=self.MAX_RETRIES
        )

    def _resolve_step_arguments(
        self,
        args: Dict[str, Any],
        step_results: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve step arguments by replacing placeholders with actual values."""

        resolved_args = {}

        for key, value in args.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                # This is a placeholder reference
                placeholder = value[1:-1]  # Remove braces

                if placeholder in step_results:
                    resolved_args[key] = step_results[placeholder]
                elif placeholder in context:
                    resolved_args[key] = context[placeholder]
                else:
                    # Keep original value if no replacement found
                    resolved_args[key] = value
                    logger.warning(f"Could not resolve placeholder: {placeholder}")
            else:
                resolved_args[key] = value

        return resolved_args

    async def _should_continue_after_error(
        self,
        plan: ExecutionPlan,
        failed_step: PlanStep,
        error: str,
        step_results: Dict[str, Any],
        current_step_index: int
    ) -> bool:
        """Use LLM to decide whether to continue execution after an error."""

        # Handle specific Gmail connection errors gracefully
        if "Gmail not connected" in error or "No connected account found" in error:
            logger.info("Gmail connection error detected - aborting and providing helpful message")
            return False

        try:
            system_prompt = """You are a Task Worker deciding whether to continue executing a plan after a step failed.

Consider:
1. Is the error recoverable?
2. Can remaining steps still be useful?
3. Is the overall task still achievable?

Respond with exactly "CONTINUE" or "ABORT" followed by a brief reason."""

            remaining_steps = len(plan.steps) - current_step_index - 1

            user_message = f"""Plan: {plan.task_description}

Failed Step: {failed_step.step_id} - {failed_step.description}
Error: {error}

Remaining Steps: {remaining_steps}
Step Results So Far: {json.dumps(step_results, default=str)}

Should I continue or abort?"""

            messages = [{"role": "user", "content": user_message}]

            response = await request_chat_completion(
                model=self.model,
                messages=messages,
                system=system_prompt,
                api_key=self.api_key,
                tools=[]
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse response
            should_continue = content.upper().startswith("CONTINUE")

            logger.info(f"Error recovery decision: {'CONTINUE' if should_continue else 'ABORT'}")
            return should_continue

        except Exception as e:
            logger.error(f"Failed to make error recovery decision: {e}")
            # Default to abort on error
            return False

    async def _generate_final_result(
        self,
        plan: ExecutionPlan,
        step_results: Dict[str, Any],
        execution_log: List[Dict[str, Any]]
    ) -> str:
        """Generate a final result summary using LLM."""

        try:
            system_prompt = """You are a Task Worker summarizing the results of a completed execution plan.

Create a clear, helpful summary that:
1. Confirms what was accomplished
2. Highlights key results
3. Uses markdown formatting for readability
4. Is user-friendly and informative

Focus on what the user cares about, not technical details."""

            user_message = f"""Original Task: {plan.task_description}

Step Results:
{json.dumps(step_results, default=str, indent=2)}

Execution Summary:
- Total steps: {len(execution_log)}
- Successful steps: {sum(1 for log in execution_log if log['success'])}
- Failed steps: {sum(1 for log in execution_log if not log['success'])}

Please provide a user-friendly summary of what was accomplished."""

            messages = [{"role": "user", "content": user_message}]

            response = await request_chat_completion(
                model=self.model,
                messages=messages,
                system=system_prompt,
                api_key=self.api_key,
                tools=[]
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            return content or "Task completed successfully."

        except Exception as e:
            logger.error(f"Failed to generate final result: {e}")
            # Fallback to a simple summary
            successful_steps = sum(1 for log in execution_log if log.get('success', False))
            return f"✅ **Task Completed**\n\nSuccessfully executed {successful_steps} out of {len(execution_log)} steps for: {plan.task_description}"