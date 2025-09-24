"""Trigger scheduler for managing reminders and scheduled tasks."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .models import Reminder, TriggerType
from ...services.supabase_client import get_supabase_client
# Removed WhatsApp dependency - now using web interface
from ...logging_config import get_logger

logger = get_logger(__name__)


class TriggerScheduler:
    """Manages scheduled reminders and triggers."""

    def __init__(self, check_interval_minutes: int = 1):
        self.client = get_supabase_client()
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        self._running = False
        self._task: asyncio.Task = None

    async def start(self) -> None:
        """Start the trigger scheduler."""

        if self._running:
            logger.warning("Trigger scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        print(f"📋 Scheduler task created and started", flush=True)
        logger.info(f"Trigger scheduler started (checking every {self.check_interval//60} minutes)")

    async def stop(self) -> None:
        """Stop the trigger scheduler."""

        if not self._running:
            return

        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Trigger scheduler stopped")

    async def create_reminder(self, reminder: Reminder) -> Optional[str]:
        """Create a new reminder."""

        if not self.client:
            logger.warning("Cannot create reminder: Supabase client not available")
            return None

        try:
            data = {
                "phone_number": reminder.phone_number,
                "title": reminder.title,
                "description": reminder.description,
                "scheduled_time": reminder.scheduled_time.isoformat(),
                "trigger_type": reminder.trigger_type.value,
                "recurrence_pattern": reminder.recurrence_pattern,
                "specialist_name": reminder.specialist_name,
                "created_at": datetime.now().isoformat(),
                "completed": False,
                "active": True
            }

            result = self.client.table('reminders').insert(data).execute()

            if result.data:
                reminder_id = result.data[0]['id']
                logger.info(f"Created reminder {reminder_id}: {reminder.title}")
                return str(reminder_id)

        except Exception as e:
            logger.error(f"Failed to create reminder: {e}")

        return None

    async def get_due_reminders(self) -> List[Dict[str, Any]]:
        """Get reminders that are due for execution."""

        if not self.client:
            return []

        try:
            now = datetime.now()  # Use local time to match scheduled times

            result = (
                self.client
                .table('reminders')
                .select('*')
                .eq('active', True)
                .eq('completed', False)
                .lte('scheduled_time', now.isoformat())
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Failed to get due reminders: {e}")
            return []

    async def execute_reminder(self, reminder_data: Dict[str, Any]) -> None:
        """Execute a due reminder or complex task."""

        try:
            reminder_id = reminder_data['id']
            phone_number = reminder_data['phone_number']
            title = reminder_data['title']
            description = reminder_data['description']
            trigger_type = reminder_data['trigger_type']
            specialist_name = reminder_data.get('specialist_name', 'reminder')

            # Check if this is a complex task for Planner-Worker execution
            if specialist_name == 'planner_worker':
                await self._execute_complex_task(reminder_data)
            else:
                # Handle simple reminder
                await self._execute_simple_reminder(reminder_data)

        except Exception as e:
            logger.error(f"Error executing reminder: {e}")

    async def _execute_complex_task(self, reminder_data: Dict[str, Any]) -> None:
        """Execute a complex task using Planner-Worker architecture."""

        try:
            reminder_id = reminder_data['id']
            phone_number = reminder_data['phone_number']
            description = reminder_data['description']

            logger.info(f"⏰ SCHEDULER: 🚀 Executing scheduled complex task {reminder_id}")
            logger.info(f"⏰ SCHEDULER: Task description: '{description}'")

            # Execute using Planner-Worker
            from ...planner import TaskPlanner
            from ...workers import TaskWorker

            planner = TaskPlanner()
            worker = TaskWorker()

            # Create context
            context = {
                "user_id": phone_number,
                "scheduled_task_id": reminder_id
            }

            # Execute the task
            plan = await planner.create_plan(description, context)
            result = await worker.execute_plan(plan, context)

            if result.success:
                # Save successful result to conversation
                success_message = f"✅ **Scheduled Task Completed**\n\n**Task**: {description}\n\n**Result**: {result.final_result}"
                await self._save_reminder_notification(phone_number, success_message)
                logger.info(f"⏰ SCHEDULER: ✅ Complex task {reminder_id} completed successfully")
            else:
                # Save error message
                error_message = f"❌ **Scheduled Task Failed**\n\n**Task**: {description}\n\n**Error**: {result.error}"
                await self._save_reminder_notification(phone_number, error_message)
                logger.error(f"⏰ SCHEDULER: ❌ Complex task {reminder_id} failed: {result.error}")

            # Mark task as completed
            await self._mark_reminder_completed(reminder_id)

        except Exception as e:
            logger.error(f"Error executing complex task: {e}")
            # Try to save error notification
            try:
                error_message = f"❌ **System Error**\n\nScheduled task failed: {str(e)}"
                await self._save_reminder_notification(reminder_data['phone_number'], error_message)
            except:
                pass

    async def _execute_simple_reminder(self, reminder_data: Dict[str, Any]) -> None:
        """Execute a simple reminder notification."""

        try:
            reminder_id = reminder_data['id']
            phone_number = reminder_data['phone_number']
            title = reminder_data['title']
            description = reminder_data['description']
            trigger_type = reminder_data['trigger_type']

            logger.info(f"⏰ SCHEDULER: 🔔 Executing reminder {reminder_id} for user {phone_number}")
            logger.info(f"⏰ SCHEDULER: Title: {title}")

            # Format reminder message with markdown
            message = f"🔔 **Reminder Alert**\n\n**{title}**\n\n{description}\n\n*Reminder ID: {reminder_id}*"

            # Save notification to conversation history for web interface
            success = await self._save_reminder_notification(phone_number, message)

            if success:
                logger.info(f"⏰ SCHEDULER: ✅ Successfully sent reminder notification: {title}")

                # Handle based on trigger type
                if trigger_type == TriggerType.ONE_TIME.value:
                    # Mark one-time reminder as completed
                    await self._mark_reminder_completed(reminder_id)
                    logger.info(f"⏰ SCHEDULER: Marked one-time reminder {reminder_id} as completed")
                elif trigger_type == TriggerType.RECURRING.value:
                    # Schedule next occurrence for recurring reminder
                    await self._schedule_next_occurrence(reminder_data)
                    logger.info(f"⏰ SCHEDULER: Scheduled next occurrence for recurring reminder {reminder_id}")

            else:
                logger.error(f"⏰ SCHEDULER: ❌ Failed to process reminder notification: {title}")

        except Exception as e:
            logger.error(f"⏰ SCHEDULER: ❌ Error executing simple reminder: {e}")
            logger.exception("Reminder execution error details:")

    async def _save_reminder_notification(self, phone_number: str, message: str) -> bool:
        """Save reminder notification to conversation history."""

        try:
            from ...services.conversation import get_conversation_memory
            from ...models.chat import ChatMessage

            memory = get_conversation_memory()

            # Create a system message for the reminder notification
            notification_message = ChatMessage(
                role="assistant",
                content=message,
                timestamp=datetime.utcnow().isoformat()
            )

            # Handle user ID mapping - check if we need to resolve to actual session ID
            session_id = await self._resolve_session_id(phone_number)

            # Save to conversation history so it appears in the chat
            await memory.record_assistant_message(session_id, message)

            logger.info(f"Saved reminder notification to conversation history for session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save reminder notification: {e}")
            return False

    async def _resolve_session_id(self, phone_number: str) -> str:
        """Resolve the actual session ID for a given phone number."""

        logger.info(f"⏰ SCHEDULER: 🔍 Resolving session ID for phone_number: {phone_number}")

        # If it's web_user, we need to find the actual active session ID
        if phone_number == "web_user":
            try:
                # Check if there's an active Gmail user session we can map to
                from ...services.gmail.client import get_active_gmail_user_id

                gmail_user_id = get_active_gmail_user_id()
                logger.info(f"⏰ SCHEDULER: Gmail user ID from cache: {gmail_user_id}")

                if gmail_user_id and gmail_user_id.startswith("web-"):
                    logger.info(f"⏰ SCHEDULER: ✅ Mapping web_user to active Gmail session: {gmail_user_id}")
                    return gmail_user_id

                # If no Gmail session, try to find the most recent conversation session
                if self.client:
                    logger.info("⏰ SCHEDULER: 🔍 Looking for recent conversation sessions...")
                    # Look for recent conversations that aren't "web_user"
                    result = (
                        self.client
                        .table('conversations')
                        .select('phone_number')
                        .neq('phone_number', 'web_user')
                        .like('phone_number', 'web-%')
                        .order('timestamp', desc=True)
                        .limit(1)
                        .execute()
                    )

                    logger.info(f"⏰ SCHEDULER: Found {len(result.data) if result.data else 0} recent sessions")

                    if result.data and len(result.data) > 0:
                        recent_session = result.data[0]['phone_number']
                        logger.info(f"⏰ SCHEDULER: ✅ Mapping web_user to most recent session: {recent_session}")
                        return recent_session

                # Fallback to web_user if no mapping found
                logger.warning("⏰ SCHEDULER: ⚠️ No active session found, using fallback: web_user")
                return "web_user"

            except Exception as e:
                logger.error(f"⏰ SCHEDULER: ❌ Error resolving session ID: {e}")
                logger.exception("Session resolution error:")
                return phone_number

        # For non-web users, return as-is
        logger.info(f"⏰ SCHEDULER: ✅ Using original phone_number: {phone_number}")
        return phone_number

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        print(f"🔄 Starting scheduler loop - will check every {self.check_interval} seconds", flush=True)

        while self._running:
            try:
                due_reminders = await self.get_due_reminders()

                if due_reminders:
                    print(f"📋 Found {len(due_reminders)} due reminders to process", flush=True)
                    for reminder in due_reminders:
                        await self.execute_reminder(reminder)
                else:
                    # Only log every 10 checks to avoid spam
                    import time
                    if int(time.time()) % 600 == 0:  # Every 10 minutes
                        print("🔍 Scheduler running - no due reminders found", flush=True)

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                print(f"❌ Scheduler error: {e}", flush=True)
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _mark_reminder_completed(self, reminder_id: str) -> None:
        """Mark a reminder as completed."""

        if not self.client:
            return

        try:
            self.client.table('reminders') \
                .update({"completed": True}) \
                .eq('id', reminder_id) \
                .execute()

            logger.info(f"Marked reminder {reminder_id} as completed")

        except Exception as e:
            logger.error(f"Failed to mark reminder completed: {e}")

    async def _schedule_next_occurrence(self, reminder_data: Dict[str, Any]) -> None:
        """Schedule the next occurrence of a recurring reminder."""

        try:
            current_time = datetime.fromisoformat(reminder_data['scheduled_time'].replace('Z', '+00:00'))
            recurrence_pattern = reminder_data.get('recurrence_pattern', 'daily')

            # Simple recurrence calculation
            if recurrence_pattern == 'daily':
                next_time = current_time + timedelta(days=1)
            elif recurrence_pattern == 'weekly':
                next_time = current_time + timedelta(weeks=1)
            elif recurrence_pattern == 'monthly':
                next_time = current_time + timedelta(days=30)  # Approximate
            else:
                # Default to daily
                next_time = current_time + timedelta(days=1)

            # Update the scheduled time
            if self.client:
                self.client.table('reminders') \
                    .update({"scheduled_time": next_time.isoformat()}) \
                    .eq('id', reminder_data['id']) \
                    .execute()

                logger.info(f"Scheduled next occurrence for reminder {reminder_data['id']}: {next_time}")

        except Exception as e:
            logger.error(f"Failed to schedule next occurrence: {e}")

    async def list_active_reminders(self, phone_number: str) -> List[Dict[str, Any]]:
        """List active reminders for a phone number."""

        if not self.client:
            return []

        try:
            result = (
                self.client
                .table('reminders')
                .select('*')
                .eq('phone_number', phone_number)
                .eq('active', True)
                .order('scheduled_time', desc=False)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Failed to list reminders: {e}")
            return []

    async def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel/deactivate a reminder."""

        if not self.client:
            return False

        try:
            self.client.table('reminders') \
                .update({"active": False}) \
                .eq('id', reminder_id) \
                .execute()

            logger.info(f"Cancelled reminder {reminder_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel reminder: {e}")
            return False