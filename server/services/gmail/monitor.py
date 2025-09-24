"""Email monitoring service for background email checking."""

import asyncio
from datetime import datetime, timedelta
from typing import Set, Dict, Any

from .client import GmailClient
from ...logging_config import get_logger

logger = get_logger(__name__)


class EmailMonitor:
    """Monitors Gmail for important new emails and sends web notifications."""

    def __init__(self, check_interval_minutes: int = 5):
        self.gmail_client = GmailClient()
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        self.seen_email_ids: Set[str] = set()
        self._running = False
        self._task: asyncio.Task = None

    async def start(self) -> None:
        """Start the email monitoring service."""

        if self._running:
            logger.warning("Email monitor already running")
            return

        # Check Gmail connection
        if not await self.gmail_client.verify_gmail_connection():
            logger.error("Cannot start email monitor: Gmail connection failed")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Email monitor started (checking every {self.check_interval//60} minutes)")

    async def stop(self) -> None:
        """Stop the email monitoring service."""

        if not self._running:
            return

        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Email monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""

        while self._running:
            try:
                await self._check_for_important_emails()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in email monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _check_for_important_emails(self) -> None:
        """Check for new important emails."""

        try:
            # Get unread emails from the last hour
            unread_emails = await self.gmail_client.get_recent_unread_emails(hours=1)

            for email in unread_emails:
                email_id = email.get('id')

                # Skip if we've already seen this email
                if email_id in self.seen_email_ids:
                    continue

                # Classify email importance
                is_important = await self._classify_email_importance(email)

                if is_important:
                    await self._send_email_notification(email)

                # Mark as seen
                self.seen_email_ids.add(email_id)

                # Keep seen_email_ids from growing too large
                if len(self.seen_email_ids) > 1000:
                    # Remove oldest entries (this is a simple approach)
                    oldest_ids = list(self.seen_email_ids)[:500]
                    self.seen_email_ids.difference_update(oldest_ids)

        except Exception as e:
            logger.error(f"Error checking for important emails: {e}")

    async def _classify_email_importance(self, email: Dict[str, Any]) -> bool:
        """Classify if an email is important enough for web notification."""

        # Simple importance classification
        # TODO: Implement AI-powered importance classification
        subject = email.get('subject', '').lower()
        sender = email.get('from', '').lower()
        snippet = email.get('snippet', '').lower()

        # High importance indicators
        urgent_keywords = ['urgent', 'asap', 'emergency', 'important', 'critical']
        meeting_keywords = ['meeting', 'call', 'zoom', 'conference']
        action_keywords = ['action required', 'please review', 'approval needed']

        # Check for urgent keywords
        text_to_check = f"{subject} {snippet}"
        for keyword in urgent_keywords + meeting_keywords + action_keywords:
            if keyword in text_to_check:
                logger.info(f"Email marked important due to keyword: {keyword}")
                return True

        # Check for VIP senders (simple domain check)
        vip_domains = ['@company.com', '@client.com']  # Configure based on user
        for domain in vip_domains:
            if domain in sender:
                logger.info(f"Email marked important due to VIP sender: {sender}")
                return True

        # Default to not important
        return False

    async def _send_email_notification(self, email: Dict[str, Any]) -> None:
        """Send web notification about an important email."""

        try:
            subject = email.get('subject', 'No Subject')
            sender = email.get('from', 'Unknown Sender')
            snippet = email.get('snippet', '')

            # Format notification message
            notification = f"📧 **Important Email**\n\n**From:** {sender}\n**Subject:** {subject}\n\n**Preview:** {snippet[:100]}..."

            # TODO: Get user's phone number from configuration or database
            # For now, we'll log the notification
            logger.info(f"Important email notification: {notification}")

            # In a real implementation, you would:
            # user_phone = await get_user_phone_number()
            # await send_web_notification(notification)

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get monitoring status."""

        return {
            "running": self._running,
            "check_interval_minutes": self.check_interval // 60,
            "seen_emails_count": len(self.seen_email_ids),
            "last_check": datetime.utcnow().isoformat()
        }