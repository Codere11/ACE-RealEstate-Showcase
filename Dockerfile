FROM node:22-alpine AS angular-build
WORKDIR /app/angular-visitor
COPY angular-visitor/package.json angular-visitor/package-lock.json ./
RUN npm ci
COPY angular-visitor/ .
RUN npx ng build --configuration=production

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt asyncpg python-jose[cryptography] livekit livekit-api

COPY backend/ ./backend/
COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY static/ ./static/
COPY --from=angular-build /app/angular-visitor/dist/angular-visitor/browser/ ./backend/static/

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/ >/dev/null || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
