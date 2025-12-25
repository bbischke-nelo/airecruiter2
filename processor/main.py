"""Main entry point for the processor service."""

import asyncio
import logging
import signal
import sys
from typing import List

import structlog

from processor.config import settings
from processor.database import get_session, SessionLocal
from processor.heartbeat import HeartbeatWriter
from processor.scheduler import Scheduler
from processor.worker import Worker

# Configure stdlib logging level (required for structlog.stdlib.filter_by_level)
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class ProcessorService:
    """Main processor service orchestrating worker, scheduler, and heartbeat."""

    def __init__(self):
        self.db = get_session()
        self.worker = Worker(SessionLocal)  # Pass factory, not instance
        self.scheduler = Scheduler(self.db)
        self.heartbeat = HeartbeatWriter(status_callback=self._get_status)
        self.running = False
        self.tasks: List[asyncio.Task] = []

    def _get_status(self) -> dict:
        """Get combined status for heartbeat."""
        return {
            "worker": self.worker.get_status(),
            "scheduler": self.scheduler.get_status(),
        }

    def _register_processors(self) -> None:
        """Register all job processors."""
        # Import processors here to avoid circular imports
        # These will be created in Phase 5 and 6
        try:
            from processor.processors.sync import SyncProcessor
            self.worker.register_processor(SyncProcessor)
        except ImportError:
            logger.warning("SyncProcessor not available")

        try:
            from processor.processors.analyze import AnalyzeProcessor
            self.worker.register_processor(AnalyzeProcessor)
        except ImportError:
            logger.warning("AnalyzeProcessor not available")

        try:
            from processor.processors.send_interview import SendInterviewProcessor
            self.worker.register_processor(SendInterviewProcessor)
        except ImportError:
            logger.warning("SendInterviewProcessor not available")

        try:
            from processor.processors.evaluate import EvaluateProcessor
            self.worker.register_processor(EvaluateProcessor)
        except ImportError:
            logger.warning("EvaluateProcessor not available")

        try:
            from processor.processors.generate_report import GenerateReportProcessor
            self.worker.register_processor(GenerateReportProcessor)
        except ImportError:
            logger.warning("GenerateReportProcessor not available")

        try:
            from processor.processors.upload_report import UploadReportProcessor
            self.worker.register_processor(UploadReportProcessor)
        except ImportError:
            logger.warning("UploadReportProcessor not available")

    async def start(self) -> None:
        """Start all processor components."""
        self.running = True
        logger.info("Starting processor service")

        # Register processors
        self._register_processors()

        # Start components as tasks
        self.tasks = [
            asyncio.create_task(self.worker.run(), name="worker"),
            asyncio.create_task(self.heartbeat.run(), name="heartbeat"),
        ]

        # Only start scheduler if enabled
        if settings.SCHEDULER_ENABLED:
            self.tasks.append(
                asyncio.create_task(self.scheduler.run(), name="scheduler")
            )
        else:
            logger.info("Scheduler disabled by configuration")

        logger.info(
            "Processor service started",
            components=[t.get_name() for t in self.tasks],
        )

        # Wait for all tasks
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")

    async def stop(self) -> None:
        """Stop all processor components gracefully."""
        logger.info("Stopping processor service")
        self.running = False

        # Stop all components
        await asyncio.gather(
            self.worker.stop(),
            self.scheduler.stop(),
            self.heartbeat.stop(),
        )

        # Cancel any remaining tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Close database session
        self.db.close()

        logger.info("Processor service stopped")


async def main() -> None:
    """Main entry point."""
    service = ProcessorService()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(service.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await service.stop()
    except Exception as e:
        logger.error("Processor service error", error=str(e), exc_info=True)
        await service.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
