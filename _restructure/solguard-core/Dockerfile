# solguard-core — Autonomous AI Sentinel for Solana program upgrades.
# Multi-stage build keeps the final image small and free of build tools.

# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed for some wheels (cryptography, grpcio via solana-py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Security: run as non-root
RUN useradd --create-home --shell /bin/bash solguard
WORKDIR /app

# Minimal runtime deps (tini for proper PID-1 signal handling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY agent/ ./agent/
COPY programs/ ./programs/

# Data dir for SQLite alert store (mounted as volume in docker-compose)
RUN mkdir -p /data && chown -R solguard:solguard /app /data

USER solguard

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SOLGUARD_DB_PATH=/data/solguard_alerts.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
