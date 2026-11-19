# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python build dependencies
COPY pyproject.toml README.md /app/
COPY src/ /app/src/

RUN pip install --no-cache-dir .

# Create workspace and data directories
RUN mkdir -p /data /tmp/termbox_workspaces

ENV TERMBOX_DB_PATH=/data/termbox_runner.db
ENV TERMBOX_HOST=0.0.0.0
ENV TERMBOX_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "termbox_runner.api:app", "--host", "0.0.0.0", "--port", "8000"]
