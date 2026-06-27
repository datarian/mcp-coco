FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# `just` isn't packaged for Debian bookworm, so install the official prebuilt binary.
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

COPY pyproject.toml uv.lock /workspace/
RUN uv sync

ENV UV_NO_MANAGED_PYTHON=1
ENV PYTHONPATH=/workspace/src
