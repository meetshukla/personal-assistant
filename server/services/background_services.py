"""Background services for email monitoring and reminder triggers."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from ..config import get_settings
from ..logging_config import get_logger
from .gmail.monitor import EmailMonitor
from .triggers.scheduler import TriggerScheduler

logger = get_logger(__name__)


class BackgroundServiceManager:
    """Manages all background services for the Personal Assistant."""

    def __init__(self):
        self.settings = get_settings()
        self.email_monitor: Optional[EmailMonitor] = None
        self.trigger_scheduler: Optional[TriggerScheduler] = None
        self._running = False

    async def start_services(self) -> None:
        """Start all background services."""

        if self._running:
            logger.warning("Background services already running")
            return

        logger.info("Starting background services...")

        try:
            # Start email monitoring if Gmail is configured
            if (self.settings.composio_api_key and
                self.settings.composio_gmail_auth_config_id):

                self.email_monitor = EmailMonitor()
                await self.email_monitor.start()
                logger.info("Email monitor started")
            else:
                logger.info("Gmail not configured, skipping email monitor (can be enabled later)")

            # Start trigger scheduler
            self.trigger_scheduler = TriggerScheduler()
            await self.trigger_scheduler.start()
            print("⏰ Trigger scheduler started - checking every 1 minute", flush=True)
            logger.info("Trigger scheduler started")

            self._running = True
            logger.info("All background services started successfully")

        except Exception as e:
            logger.error(f"Failed to start background services: {e}")
            await self.stop_services()

    async def stop_services(self) -> None:
        """Stop all background services."""

        if not self._running:
            return

        logger.info("Stopping background services...")

        try:
            if self.email_monitor:
                await self.email_monitor.stop()
                self.email_monitor = None
                logger.info("Email monitor stopped")

            if self.trigger_scheduler:
                await self.trigger_scheduler.stop()
                self.trigger_scheduler = None
                logger.info("Trigger scheduler stopped")

        except Exception as e:
            logger.error(f"Error stopping background services: {e}")

        self._running = False
        logger.info("Background services stopped")

    def is_running(self) -> bool:
        """Check if background services are running."""
        return self._running


# Global background service manager
_background_manager = BackgroundServiceManager()


def get_background_manager() -> BackgroundServiceManager:
    """Get the global background service manager."""
    return _background_manager