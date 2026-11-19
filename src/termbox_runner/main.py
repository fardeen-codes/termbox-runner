"""CLI entrypoint for termbox-runner application."""

import sys
import uvicorn
from termbox_runner.config import get_settings


def main():
    """Run FastAPI server using uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "termbox_runner.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
