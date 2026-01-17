# NOTION FEATURES: ND03
# MODULES: NotionDev
# DESCRIPTION: Docker image for NotionDev MCP Server (remote mode)
# LAST_SYNC: 2025-12-31

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Create app user (non-root for security)
RUN useradd --create-home --shell /bin/bash appuser

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files for installation
COPY pyproject.toml .
COPY setup.py .
COPY README.md .
COPY notion_dev/ ./notion_dev/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install ".[mcp]" && \
    pip install httpx PyJWT

# Create directories for data and fix permissions
RUN mkdir -p /data/repos && \
    chown -R appuser:appuser /data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for SSE transport
EXPOSE 8000

# Note: Health checks are handled by fly.io, not Docker
# The MCP SSE endpoint at /sse is used for health monitoring

# Default command: run MCP server in remote mode
# Auth is controlled by MCP_AUTH_ENABLED env var (default: false)
CMD ["python", "-m", "notion_dev.mcp_server.server", "--transport", "sse", "--port", "8000"]
