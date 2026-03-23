# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev extras, no editable install yet)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY operator_use/ ./operator_use/
COPY main.py ./

# Install the project itself
RUN uv sync --frozen --no-dev

# Ports (only needed when the respective feature is enabled in config):
# 8080  - Webhook server for Telegram, Discord, Slack (use_webhook=true)
# 8765  - ACP server (Agent Communication Protocol, disabled by default)
# 1883  - MQTT broker connection (plain)
# 8883  - MQTT broker connection (TLS)
# 9222  - Chrome DevTools Protocol / browser remote debugging
EXPOSE 8080 8765 1883 8883 9222

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["uv", "run", "operator"]
