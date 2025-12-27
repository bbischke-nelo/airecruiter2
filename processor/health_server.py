"""Simple HTTP health server for processor container health checks."""

import asyncio
from aiohttp import web
import structlog

logger = structlog.get_logger()

# Default port for health server
HEALTH_PORT = 8080


class HealthServer:
    """Lightweight HTTP server for health checks."""

    def __init__(self, status_callback=None, port: int = HEALTH_PORT):
        self.status_callback = status_callback
        self.port = port
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.runner = None
        self.running = False

    async def health_handler(self, request):
        """Handle health check requests."""
        status = {"status": "ok"}
        if self.status_callback:
            try:
                status["details"] = self.status_callback()
            except Exception as e:
                logger.warning("Failed to get status details", error=str(e))
        return web.json_response(status)

    async def run(self):
        """Start the health server."""
        self.running = True
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()
        logger.info("Health server started", port=self.port)

        # Keep running until stopped
        while self.running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the health server."""
        self.running = False
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health server stopped")
