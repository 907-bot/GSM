#=============================================================================
# GSM-OS Production Dockerfile  — Lightweight (no PyTorch, ~200MB image)
# Uses HuggingFace HTTP API for embeddings instead of local sentence-transformers.
# Builds in ~90 seconds. No ML framework bloat in the container.
#=============================================================================

# ── Builder stage ─────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Single pip install step with --ignore-installed to guarantee all transitive
# deps (including packaging, setuptools) end up in /install, not just system-wide.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install --ignore-installed \
      fastapi "uvicorn[standard]" \
      gunicorn \
      packaging \
      pydantic pydantic-settings \
      groq \
      langchain langchain-groq langchain-community langchain-core langgraph \
      "qdrant-client>=1.7.0,<1.9.0" \
      neo4j \
      httpx aiohttp feedparser \
      celery[redis] \
      python-dotenv structlog rich typer pyyaml orjson \
      prometheus-client ollama \
      pyjwt bcrypt \
      numpy

# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1001 appuser && \
    useradd -u 1001 -g appuser -s /bin/bash -m appuser

COPY --from=builder /install /usr/local
COPY src/ ./src/
COPY pyproject.toml .
COPY scripts/healthcheck.sh ./scripts/healthcheck.sh
RUN chmod +x ./scripts/healthcheck.sh

RUN mkdir -p /app/audit_logs /app/data /app/backups /app/logs && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/liveness || exit 1

CMD ["gunicorn", "src.api.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--workers", "2", "--bind", "0.0.0.0:8000", "--timeout", "120", "--max-requests", "1000", "--max-requests-jitter", "100"]
