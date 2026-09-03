# Build from the repo root (mcp_server is spawned over stdio *within* this
# same container, exactly as AGENTS_WORKING_DIR/MCP_SERVER_PYTHON_EXECUTABLE
# work in local dev — see shared/mcp_client.py — so both packages need to be
# installed into one image, not deployed as two separate Cloud Run services):
#   docker build -f agents/Dockerfile -t scenecraft-agents .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY mcp_server/pyproject.toml ./mcp_server/pyproject.toml
COPY mcp_server/src ./mcp_server/src
RUN pip install ./mcp_server

COPY agents/pyproject.toml ./agents/pyproject.toml
COPY agents/orchestrator ./agents/orchestrator
COPY agents/breakdown_agent ./agents/breakdown_agent
COPY agents/frame_agent ./agents/frame_agent
COPY agents/app_build_agent ./agents/app_build_agent
COPY agents/critic_agent ./agents/critic_agent
COPY agents/iteration_agent ./agents/iteration_agent
COPY agents/shared ./agents/shared
RUN pip install ./agents

WORKDIR /app/agents

# The deployed entrypoint (Pub/Sub push receiver) — see
# orchestrator/pubsub_receiver.py's docstring. Local dev keeps using
# `python -m orchestrator.coordinator` via apps/api's subprocess spawn;
# this container is the Cloud Run "Agent Workers" service (10-DIAGRAMS.md
# SS8's CR3) only.
ENV PORT=8080
ENV MCP_SERVER_PYTHON_EXECUTABLE=python
ENV MCP_SERVER_WORKING_DIR=/app/mcp_server
EXPOSE 8080

CMD ["sh", "-c", "uvicorn orchestrator.pubsub_receiver:app --host 0.0.0.0 --port ${PORT}"]
