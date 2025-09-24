#!/usr/bin/env python3
"""Run the FastAPI server directly."""

import uvicorn
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from server.config import get_settings

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