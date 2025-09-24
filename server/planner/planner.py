"""Task Planner - Creates detailed execution plans for complex tasks."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..openrouter_client import request_chat_completion
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    tool: str
    args: Dict[str, Any]
    description: str
    step_id: str


@dataclass
class ExecutionPlan:
    """Complete execution plan with steps and metadata."""

    task_description: str
    steps: List[PlanStep]
    plan_id: str
    estimated_duration: Optional[str] = None


class TaskPlanner:
    """LLM-powered task planner that creates detailed execution plans."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openrouter_api_key
        self.model = settings.message_conductor_model  # Use same model as conductor

        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

    async def create_plan(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """Create a detailed execution plan for the given task."""

        try:
            logger.info(f"📋 PLANNER: Starting plan creation for task: '{task_description}'")

            system_prompt = self._get_planner_system_prompt()

            # Build user message with context
            user_message = f"Task: {task_description}"
            if context:
                user_message += f"\nContext: {json.dumps(context, default=str)}"
                logger.info(f"📋 PLANNER: Using context: {list(context.keys())}")

            messages = [{"role": "user", "content": user_message}]

            response = await request_chat_completion(
                model=self.model,
                messages=messages,
                system=system_prompt,
                api_key=self.api_key,
                tools=[]  # Planner doesn't call tools, just creates plans
            )

            # Extract plan from response
            assistant_message = response.get("choices", [{}])[0].get("message", {})
            content = assistant_message.get("content", "")

            if not content:
                raise ValueError("Empty response from planner")

            # Parse the plan from the response
            plan = await self._parse_plan_response(content, task_description)

            logger.info(f"📋 PLANNER: ✅ Plan created successfully!")
            logger.info(f"📋 PLANNER: Plan ID: {plan.plan_id}")
            logger.info(f"📋 PLANNER: Steps: {len(plan.steps)}")
            logger.info(f"📋 PLANNER: Estimated duration: {plan.estimated_duration}")
            for i, step in enumerate(plan.steps, 1):
                logger.info(f"📋 PLANNER: Step {i}: {step.tool} - {step.description}")
            return plan

        except Exception as e:
            logger.error(f"Failed to create plan for task '{task_description}': {e}")
            # Return a fallback plan
            return self._create_fallback_plan(task_description)

    def _get_planner_system_prompt(self) -> str:
        """Get the system prompt for the planner."""

        return """You are a Task Planner. Your ONLY job is to create detailed execution plans.

**CRITICAL RULES:**
1. You NEVER execute tasks - you ONLY create plans
2. You MUST output plans in the exact JSON format specified
3. Plans must be sequential and logical
4. Each step must specify a tool and arguments

**Available Tools:**
- gmail_tool.fetch_emails(user_id, query, max_results) - Get emails from Gmail
- gmail_tool.search_emails(user_id, query) - Search Gmail
- gmail_tool.send_email(user_id, to, subject, body) - Send email
- gmail_tool.get_profile(user_id) - Get Gmail profile
- gmail_tool.check_recent_emails(user_id, since_hours) - Check recent unread emails
- llm_tool.summarize(text, max_length) - Summarize text
- llm_tool.analyze(text, task) - Analyze text for specific task
- llm_tool.classify(text, categories) - Classify text into categories
- llm_tool.extract_information(text, fields) - Extract specific information
- llm_tool.generate_response(prompt, context) - Generate responses
- scheduler_tool.schedule_task(task_description, delay_minutes, user_id) - Schedule future execution
- scheduler_tool.store_complex_task(description, execution_time, user_id) - Store for later
- scheduler_tool.create_reminder(title, description, scheduled_time, user_id) - Create reminders
- scheduler_tool.list_scheduled_tasks(user_id) - List scheduled tasks
- scheduler_tool.cancel_task(task_id, user_id) - Cancel tasks
- scheduler_tool.update_task(task_id, new_time, new_description, user_id) - Update tasks

**IMPORTANT**: If Gmail tools fail, gracefully fall back to informing the user that Gmail connection is required.

**Output Format (STRICT JSON):**
{
  "plan_id": "unique_id",
  "task_description": "original task",
  "estimated_duration": "X minutes",
  "steps": [
    {
      "step_id": "1",
      "tool": "tool_name.function_name",
      "args": {"param1": "value1", "param2": "value2"},
      "description": "What this step does"
    }
  ]
}

**Example Plans:**

For "Check my emails from today":
{
  "plan_id": "check_emails_001",
  "task_description": "Check my emails from today",
  "estimated_duration": "2 minutes",
  "steps": [
    {
      "step_id": "1",
      "tool": "gmail_tool.fetch_emails",
      "args": {"user_id": "web_user", "query": "after:today", "max_results": 20},
      "description": "Fetch recent emails from today"
    }
  ]
}

For "Summarize my emails and send report to alice@example.com":
{
  "plan_id": "email_summary_001",
  "task_description": "Summarize my emails and send report to alice@example.com",
  "estimated_duration": "5 minutes",
  "steps": [
    {
      "step_id": "1",
      "tool": "gmail_tool.fetch_emails",
      "args": {"user_id": "web_user", "query": "after:today", "max_results": 20},
      "description": "Fetch recent emails to summarize"
    },
    {
      "step_id": "2",
      "tool": "llm_tool.summarize",
      "args": {"text": "{step_1_result}", "max_length": 300},
      "description": "Create summary of emails"
    },
    {
      "step_id": "3",
      "tool": "gmail_tool.send_email",
      "args": {"user_id": "web_user", "to": "alice@example.com", "subject": "Email Summary Report", "body": "{step_2_result}"},
      "description": "Send summary report via email"
    }
  ]
}

**Important Notes:**
- Use "web_user" as default user_id for tools
- Reference previous step results as "{step_X_result}"
- Be specific with tool arguments
- Always include step descriptions
- Plans must be actionable and complete

Create a plan for the given task now."""

    async def _parse_plan_response(self, content: str, task_description: str) -> ExecutionPlan:
        """Parse the LLM response into an ExecutionPlan object."""

        try:
            # Try to extract JSON from the response
            # Look for JSON block in the response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = content[json_start:json_end]
            plan_data = json.loads(json_str)

            # Validate required fields
            if not all(key in plan_data for key in ["plan_id", "steps"]):
                raise ValueError("Missing required fields in plan")

            # Convert to ExecutionPlan
            steps = []
            for step_data in plan_data.get("steps", []):
                step = PlanStep(
                    tool=step_data.get("tool", ""),
                    args=step_data.get("args", {}),
                    description=step_data.get("description", ""),
                    step_id=step_data.get("step_id", "")
                )
                steps.append(step)

            return ExecutionPlan(
                task_description=plan_data.get("task_description", task_description),
                steps=steps,
                plan_id=plan_data.get("plan_id", f"plan_{hash(task_description)}"),
                estimated_duration=plan_data.get("estimated_duration")
            )

        except Exception as e:
            logger.error(f"Failed to parse plan response: {e}")
            logger.debug(f"Response content: {content}")
            raise ValueError(f"Invalid plan format: {e}")

    def _create_fallback_plan(self, task_description: str) -> ExecutionPlan:
        """Create a simple fallback plan when planning fails."""

        # Create a basic plan that just uses LLM to handle the task
        fallback_step = PlanStep(
            tool="llm_tool.analyze",
            args={"text": task_description, "task": "process_user_request"},
            description="Process user request with general analysis",
            step_id="fallback_1"
        )

        return ExecutionPlan(
            task_description=task_description,
            steps=[fallback_step],
            plan_id=f"fallback_{hash(task_description)}",
            estimated_duration="1 minute"
        )