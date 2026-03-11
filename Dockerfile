# ── Stage 1: Frontend build ──────────────────────
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python wheels ──────────────────────
FROM python:3.13-slim AS python-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# ── Stage 3: Production ─────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Install git (needed for plugin installation from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID/GID match typical host user)
ARG UID=1000
ARG GID=1000
RUN groupadd --gid ${GID} mdkb && useradd --uid ${UID} --gid mdkb mdkb

# Install pre-built wheels (no compilers needed)
COPY --from=python-builder /app/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy application code
COPY app/ ./app/
COPY mcp_server.py ./mcp_server.py
COPY config/settings.yaml.example ./config/settings.yaml.example
COPY config/prompts/ ./config/prompts/

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist/ ./frontend/dist/

# Create data directories
RUN mkdir -p /app/data/chromadb /app/data/plans /app/data/plugins /app/docs /app/skills \
    && chown -R mdkb:mdkb /app/data /app/docs /app/skills

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 9713

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:9713/api/health').raise_for_status()"

USER mdkb

CMD ["python", "-m", "app.main"]
