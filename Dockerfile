# syntax=docker/dockerfile:1

# ---- Builder stage: install with uv ----
FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY uv.lock pyproject.toml ./
RUN UV_PROJECT_ENVIRONMENT=/app/.venv uv sync --frozen --no-dev

# ---- Runtime stage ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ src/
COPY scripts/ scripts/

EXPOSE 8000

# Default: streamable-http on 0.0.0.0:8000 for MCP gateway access.
# Override with e.g. CMD ["mcp-coco-server", "--transport", "stdio"] for stdio.
CMD ["mcp-coco-server", "--transport", "streamable-http", "--host", "0.0.0.0"]
