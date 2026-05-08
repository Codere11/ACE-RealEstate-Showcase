# Backend (FastAPI) Dockerfile
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for bcrypt/psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# App deps
# No requirements.txt present, install known runtime deps explicitly
RUN pip install \
    fastapi \
    "uvicorn[standard]" \
    sqlalchemy \
    pydantic \
    pyjwt \
    bcrypt \
    aiofiles \
    psycopg2-binary

# Copy source
COPY ./ /app/

# Expose API port
EXPOSE 8000

# Default env (can be overridden via compose)
ENV ACE_LOG_LEVEL=INFO \
    ACE_ENFORCE_DUAL_CONTACT=1 \
    DATABASE_URL=sqlite:////data/ace.db

# Create runtime dirs
RUN mkdir -p /data /app/static

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
