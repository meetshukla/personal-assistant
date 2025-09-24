"""FastAPI server entry point for Personal Assistant."""

import uvicorn

from .app import app
from .config import get_settings


def main():
    """Run the FastAPI server."""
    settings = get_settings()

    uvicorn.run(
        "server.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()