"""Heartbeat writer for health monitoring."""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional, Callable

import structlog

from processor.config import settings

logger = structlog.get_logger()


class HeartbeatWriter:
    """Writes periodic heartbeat to file for external monitoring."""

    def __init__(self, status_callback: Optional[Callable[[], dict]] = None):
        """Initialize heartbeat writer.

        Args:
            status_callback: Optional callback to get additional status info
        """
        self.file_path = settings.HEARTBEAT_FILE
        self.interval = settings.HEARTBEAT_INTERVAL
        self.status_callback = status_callback
        self.running = False
        self.pid = os.getpid()
        self.last_activity: Optional[str] = None

    async def run(self) -> None:
        """Main heartbeat loop."""
        self.running = True
        logger.info("Heartbeat writer started", file=self.file_path, interval=self.interval)

        while self.running:
            try:
                await self._write_heartbeat()
            except Exception as e:
                logger.error("Heartbeat write failed", error=str(e))

            await asyncio.sleep(self.interval)

        logger.info("Heartbeat writer stopped")

    async def stop(self) -> None:
        """Stop the heartbeat writer."""
        self.running = False

    async def _write_heartbeat(self) -> None:
        """Write heartbeat data to file."""
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pid": self.pid,
            "status": "running",
            "last_activity": self.last_activity,
        }

        # Add additional status if callback provided
        if self.status_callback:
            try:
                data.update(self.status_callback())
            except Exception as e:
                logger.error("Status callback failed", error=str(e))

        # Write atomically (write to temp, then rename)
        temp_path = f"{self.file_path}.tmp"
        with open(temp_path, "w") as f:
            json.dump(data, f)

        os.replace(temp_path, self.file_path)

    def set_activity(self, activity: str) -> None:
        """Update last activity message.

        Args:
            activity: Description of last activity
        """
        self.last_activity = activity
