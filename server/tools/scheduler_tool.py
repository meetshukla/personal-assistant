"""Scheduler Tool Functions - Pure functions for task scheduling."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..logging_config import get_logger
from ..services.supabase_client import get_supabase_client

logger = get_logger(__name__)


def parse_natural_time(time_str: str) -> datetime:
    """Parse natural language time expressions into datetime objects."""

    if not time_str:
        raise ValueError("Empty time string provided")

    time_str = time_str.lower().strip()
    now = datetime.now()

    # Try to parse as ISO format first
    try:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except:
        pass

    # Parse relative time expressions
    patterns = [
        # "now + 5 minutes", "now + 1 minute", "now+5minutes"
        (r'now\s*\+\s*(\d+)\s*minute[s]?', lambda m: now + timedelta(minutes=int(m.group(1)))),
        # "now + 2 hours", "now + 1 hour"
        (r'now\s*\+\s*(\d+)\s*hour[s]?', lambda m: now + timedelta(hours=int(m.group(1)))),
        # "now + 1 day", "now + 3 days"
        (r'now\s*\+\s*(\d+)\s*day[s]?', lambda m: now + timedelta(days=int(m.group(1)))),
        # "5 minutes from now", "10 minutes", "in 5 minutes"
        (r'(?:in\s+)?(\d+)\s+minute[s]?(?:\s+from\s+now)?', lambda m: now + timedelta(minutes=int(m.group(1)))),
        # "2 hours from now", "3 hours", "in 2 hours"
        (r'(?:in\s+)?(\d+)\s+hour[s]?(?:\s+from\s+now)?', lambda m: now + timedelta(hours=int(m.group(1)))),
        # "1 day from now", "2 days", "in 3 days"
        (r'(?:in\s+)?(\d+)\s+day[s]?(?:\s+from\s+now)?', lambda m: now + timedelta(days=int(m.group(1)))),
        # "1 week from now", "2 weeks"
        (r'(?:in\s+)?(\d+)\s+week[s]?(?:\s+from\s+now)?', lambda m: now + timedelta(weeks=int(m.group(1)))),
        # "tomorrow at 9am", "tomorrow 9:00"
        (r'tomorrow(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:am|pm)?)?',
         lambda m: (now + timedelta(days=1)).replace(
             hour=int(m.group(1)) if m.group(1) else 9,
             minute=int(m.group(2)) if m.group(2) else 0,
             second=0, microsecond=0
         )),
        # "today at 3pm", "today 15:00"
        (r'today(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:am|pm)?)?',
         lambda m: now.replace(
             hour=int(m.group(1)) if m.group(1) else (now.hour + 1),
             minute=int(m.group(2)) if m.group(2) else 0,
             second=0, microsecond=0
         )),
        # "next monday", "next tuesday", etc.
        (r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
         lambda m: now + timedelta(days=(7 - now.weekday() + ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].index(m.group(1))) % 7))
    ]

    for pattern, calculator in patterns:
        match = re.search(pattern, time_str)
        if match:
            result = calculator(match)
            logger.info(f"Parsed '{time_str}' as {result}")
            return result

    # If no pattern matches, try some common formats
    common_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%H:%M:%S",
        "%H:%M"
    ]

    for fmt in common_formats:
        try:
            if len(time_str.split()) == 1 and ':' in time_str:
                # Time only - assume today
                time_part = datetime.strptime(time_str, fmt).time()
                result = now.replace(hour=time_part.hour, minute=time_part.minute, second=time_part.second, microsecond=0)
                # If the time has already passed today, schedule for tomorrow
                if result <= now:
                    result += timedelta(days=1)
                return result
            else:
                return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Could not parse time expression: '{time_str}'. Please use formats like '5 minutes from now', 'tomorrow at 9am', or ISO format '2025-01-01T10:00:00'")


async def schedule_task(task_description: str, delay_minutes: int, user_id: str = "web_user", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Schedule a task for future execution."""

    try:
        supabase = get_supabase_client()

        if not supabase:
            raise RuntimeError("Database connection not available")

        # Calculate execution time
        execution_time = datetime.now() + timedelta(minutes=delay_minutes)

        # Prepare data for storage
        data = {
            "phone_number": user_id,
            "title": f"Scheduled Task",
            "description": task_description,
            "scheduled_time": execution_time.isoformat(),
            "trigger_type": "one_time",
            "specialist_name": "planner_worker",  # This will trigger Planner -> Worker flow
            "created_at": datetime.now().isoformat(),
            "completed": False,
            "active": True
        }

        # Add context if provided
        if context:
            import json
            data["context"] = json.dumps(context, default=str)

        # Insert into database
        result = supabase.table('reminders').insert(data).execute()

        if result.data:
            task_id = result.data[0]['id']
            logger.info(f"Scheduled task {task_id} for execution in {delay_minutes} minutes")

            return {
                "success": True,
                "task_id": task_id,
                "scheduled_time": execution_time.isoformat(),
                "delay_minutes": delay_minutes,
                "message": f"Task scheduled for execution in {delay_minutes} minutes"
            }
        else:
            raise RuntimeError("Failed to insert task into database")

    except Exception as e:
        logger.error(f"Failed to schedule task: {e}")
        raise RuntimeError(f"Task scheduling failed: {str(e)}")


async def store_complex_task(description: str, execution_time: str, user_id: str = "web_user", execution_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Store a complex task with optional execution plan for later execution."""

    try:
        supabase = get_supabase_client()

        if not supabase:
            raise RuntimeError("Database connection not available")

        # Parse execution time using natural language parser
        try:
            exec_dt = parse_natural_time(execution_time)
            logger.info(f"Successfully parsed execution time '{execution_time}' as {exec_dt}")
        except Exception as parse_error:
            logger.error(f"Failed to parse execution time '{execution_time}': {parse_error}")
            raise ValueError(f"Invalid execution time format: {execution_time}. {str(parse_error)}")

        # Prepare data
        data = {
            "phone_number": user_id,
            "title": "Complex Scheduled Task",
            "description": description,
            "scheduled_time": exec_dt.isoformat(),
            "trigger_type": "one_time",
            "specialist_name": "planner_worker",
            "created_at": datetime.now().isoformat(),
            "completed": False,
            "active": True
        }

        # Store execution plan if provided
        if execution_plan:
            import json
            data["execution_plan"] = json.dumps(execution_plan, default=str)

        # Insert into database
        result = supabase.table('reminders').insert(data).execute()

        if result.data:
            task_id = result.data[0]['id']
            logger.info(f"Stored complex task {task_id} for execution at {exec_dt}")

            return {
                "success": True,
                "task_id": task_id,
                "execution_time": exec_dt.isoformat(),
                "message": f"Complex task stored for execution at {exec_dt.strftime('%Y-%m-%d %H:%M:%S')}"
            }
        else:
            raise RuntimeError("Failed to insert complex task into database")

    except Exception as e:
        logger.error(f"Failed to store complex task: {e}")
        raise RuntimeError(f"Complex task storage failed: {str(e)}")


async def create_reminder(title: str, description: str, scheduled_time: str, user_id: str = "web_user", recurring: bool = False, recurrence_pattern: Optional[str] = None) -> Dict[str, Any]:
    """Create a simple reminder (compatibility with existing reminder system)."""

    try:
        supabase = get_supabase_client()

        if not supabase:
            raise RuntimeError("Database connection not available")

        # Parse scheduled time using natural language parser
        try:
            scheduled_dt = parse_natural_time(scheduled_time)
            logger.info(f"Successfully parsed scheduled time '{scheduled_time}' as {scheduled_dt}")
        except Exception as parse_error:
            logger.error(f"Failed to parse scheduled time '{scheduled_time}': {parse_error}")
            raise ValueError(f"Invalid scheduled time format: {scheduled_time}. {str(parse_error)}")

        # Prepare data
        data = {
            "phone_number": user_id,
            "title": title,
            "description": description,
            "scheduled_time": scheduled_dt.isoformat(),
            "trigger_type": "recurring" if recurring else "one_time",
            "recurrence_pattern": recurrence_pattern,
            "specialist_name": "reminder",  # Simple reminder, not complex task
            "created_at": datetime.now().isoformat(),
            "completed": False,
            "active": True
        }

        # Insert into database
        result = supabase.table('reminders').insert(data).execute()

        if result.data:
            reminder_id = result.data[0]['id']
            logger.info(f"Created reminder {reminder_id}: {title}")

            return {
                "success": True,
                "reminder_id": reminder_id,
                "title": title,
                "scheduled_time": scheduled_dt.isoformat(),
                "recurring": recurring,
                "message": f"Reminder '{title}' created for {scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')}"
            }
        else:
            raise RuntimeError("Failed to insert reminder into database")

    except Exception as e:
        logger.error(f"Failed to create reminder: {e}")
        raise RuntimeError(f"Reminder creation failed: {str(e)}")


async def list_scheduled_tasks(user_id: str = "web_user", include_completed: bool = False) -> Dict[str, Any]:
    """List scheduled tasks and reminders for a user."""

    try:
        supabase = get_supabase_client()

        if not supabase:
            raise RuntimeError("Database connection not available")

        # Build query
        query = supabase.table('reminders').select('*').eq('phone_number', user_id)

        if not include_completed:
            query = query.eq('completed', False)

        query = query.eq('active', True).order('scheduled_time', desc=False)

        result = query.execute()

        tasks = result.data or []

        # Format tasks for display
        formatted_tasks = []
        for task in tasks:
            try:
                scheduled_dt = datetime.fromisoformat(task['scheduled_time'].replace('Z', '+00:00'))
                formatted_time = scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_time = task['scheduled_time']

            formatted_tasks.append({
                "id": task['id'],
                "title": task['title'],
                "description": task['description'],
                "scheduled_time": formatted_time,
                "type": task['trigger_type'],
                "completed": task['completed']
            })

        logger.info(f"Listed {len(formatted_tasks)} scheduled tasks for user {user_id}")

        return {
            "success": True,
            "count": len(formatted_tasks),
            "tasks": formatted_tasks,
            "message": f"Found {len(formatted_tasks)} scheduled tasks"
        }

    except Exception as e:
        logger.error(f"Failed to list scheduled tasks: {e}")
        raise RuntimeError(f"Task listing failed: {str(e)}")


async def cancel_task(task_id: str, user_id: str = "web_user") -> Dict[str, Any]:
    """Cancel a scheduled task or reminder."""

    try:
        supabase = get_supabase_client()

        if not supabase:
            raise RuntimeError("Database connection not available")

        # Update task to inactive
        result = supabase.table('reminders')\
            .update({"active": False})\
            .eq('id', task_id)\
            .eq('phone_number', user_id)\
            .execute()

        if result.data:
            logger.info(f"Cancelled task {task_id} for user {user_id}")

            return {
                "success": True,
                "task_id": task_id,
                "message": f"Task {task_id} has been cancelled"
            }
        else:
            raise RuntimeError(f"Task {task_id} not found or already cancelled")

    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        raise RuntimeError(f"Task cancellation failed: {str(e)}")


async def update_task(task_id: str, new_time: Optional[str] = None, new_description: Optional[str] = None, user_id: str = "web_user") -> Dict[str, Any]:
    """Update a scheduled task or reminder."""

    try:
        supabase = get_supabase_client()

        if not supabase:
            raise RuntimeError("Database connection not available")

        # Prepare update data
        update_data = {}

        if new_time:
            try:
                new_dt = datetime.fromisoformat(new_time.replace('Z', '+00:00'))
                update_data["scheduled_time"] = new_dt.isoformat()
            except Exception:
                raise ValueError(f"Invalid new time format: {new_time}")

        if new_description:
            update_data["description"] = new_description

        if not update_data:
            raise ValueError("No updates provided")

        # Update task
        result = supabase.table('reminders')\
            .update(update_data)\
            .eq('id', task_id)\
            .eq('phone_number', user_id)\
            .eq('active', True)\
            .execute()

        if result.data:
            logger.info(f"Updated task {task_id} for user {user_id}")

            return {
                "success": True,
                "task_id": task_id,
                "updates": update_data,
                "message": f"Task {task_id} has been updated"
            }
        else:
            raise RuntimeError(f"Task {task_id} not found or inactive")

    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
        raise RuntimeError(f"Task update failed: {str(e)}")


# Tool function registry for discovery
SCHEDULER_TOOLS = {
    "schedule_task": schedule_task,
    "store_complex_task": store_complex_task,
    "create_reminder": create_reminder,
    "list_scheduled_tasks": list_scheduled_tasks,
    "cancel_task": cancel_task,
    "update_task": update_task,
}