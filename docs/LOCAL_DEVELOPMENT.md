<!-- Created: 2026-04-18T12:20:22Z -->
# Local Development Runbook
This runbook is the fastest path to running ACE Real Estate locally.

## Prerequisites
- Docker
- Docker Compose (v2+)

## 1) Environment Setup
Create your local environment file:

```bash
cp .env.example .env
```

Minimum fields to review in `.env`:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `ACE_LLM_PROVIDER`
- `ACE_LLM_MODEL`
- `ACE_SECRET`
- `ACE_LOG_LEVEL`
- `ACE_ENFORCE_DUAL_CONTACT`

## 2) Start the Full Stack
Recommended onboarding command:

```bash
docker compose -f docker-compose-simple.yml up -d --build
```

## 3) Service Endpoints
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Chatbot frontend: `http://localhost:4200`
- Manager dashboard: `http://localhost:4400`
- Admin portal: `http://localhost:4500`

Useful demo routes:
- Demo chatbot org route: `http://localhost:4200/demo-agency/nepremicnine`
- Manager login: `http://localhost:4400/login`
- Demo manager credentials: `admin / test123`

## 4) Health Checks
Quick checks:

```bash
curl -sf http://localhost:8000/docs
curl -sf http://localhost:4200
curl -sf http://localhost:4400
curl -sf http://localhost:4500
```

## 5) Logs and Troubleshooting
View all logs:

```bash
docker compose -f docker-compose-simple.yml logs -f
```

View backend logs only:

```bash
docker compose -f docker-compose-simple.yml logs -f backend
```

Restart stack:

```bash
docker compose -f docker-compose-simple.yml restart
```

Stop stack:

```bash
docker compose -f docker-compose-simple.yml down
```

## 6) Data Notes
- Local PostgreSQL is mapped in Docker volume `postgres_data`
- Keep secrets out of git
- Use `.env.example` as baseline for sharing config
- The AI qualifier is DB-backed and can be seeded for local demo/testing

Seed the default demo qualifier:

```bash
docker compose -f docker-compose-simple.yml exec backend python scripts/seed_default_qualifier.py
```

The chatbot will switch to open qualifier mode automatically when a live qualifier exists for the organization.

## 7) Alternative Compose Files
- `docker-compose-simple.yml`: easiest full-stack local run
- `docker-compose.yml`: full/default compose
- `docker-compose.dev.yml`: development variant
- `docker-compose.hotreload.yml`: hot-reload focused variant
