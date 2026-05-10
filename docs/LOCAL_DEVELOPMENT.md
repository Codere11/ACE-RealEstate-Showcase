# Local Development Runbook

This document now describes the **current recommended Java-first local path**.

If you want the old Angular/Python-first stack, it still exists in the repo, but it is no longer the main development truth.

## Current recommended stack
- Java app: `java-platform/`
- Python AI/runtime service: `app/`
- PostgreSQL via Docker
- LiveKit via Docker when testing live-help flow

## Prerequisites
- Java 21
- Maven wrapper works from repo (`./mvnw`)
- Python 3
- Docker + Docker Compose v2

## 1. Environment file
The Java app imports `.env`.
The Python service also uses it.

If needed:
```bash
cp .env.example .env
```

Important vars commonly used now:
- `ACE_DB_URL`
- `ACE_DB_USERNAME`
- `ACE_DB_PASSWORD`
- `OPENAI_API_KEY`
- `ACE_LLM_PROVIDER`
- `ACE_LLM_MODEL`
- `ACE_PUBLIC_BASE_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_CONNECT_CLIENT_ID`
- `STRIPE_WEBHOOK_SECRET`

## 2. Start infra
Use Docker only for infra first:

```bash
docker compose -f docker-compose-simple.yml up -d postgres livekit
```

## 3. Create Java database once
Legacy compose still creates `ace_production` by default.
The Java app expects `ace_platform` locally.

Create it once:

```bash
docker exec -it ace-postgres psql -U ace_user -c "CREATE DATABASE ace_platform;"
```

If it already exists, PostgreSQL will tell you.
That is fine.

## 4. Run the Java app
```bash
cd java-platform
./mvnw spring-boot:run
```

Expected local URL:
- `http://127.0.0.1:8080`

Health check:
```bash
curl -sf http://127.0.0.1:8080/actuator/health
```

## 5. Optional: run Python AI/runtime service
Run this when working on qualifier/runtime behavior or Java-to-Python integration paths.

```bash
cd /home/maksich/Documents/ACE-RealEstate
./run_backend.sh
```

Expected local URL:
- `http://127.0.0.1:8000`

Docs:
- `http://127.0.0.1:8000/docs`

## 6. Useful local routes
### Java app
- Home: `http://127.0.0.1:8080/`
- Demo public route: `http://127.0.0.1:8080/demo`
- Demo dashboard: `http://127.0.0.1:8080/demo/dashboard`
- Login: `http://127.0.0.1:8080/login`
- Demo credentials: `admin / test123`

### Python runtime service
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## 7. Tests
### Java
```bash
cd java-platform
./mvnw test -q
```

### Python
Run only when working in the Python service area.
The repo still contains older Python-first tests and flows.

## 8. Notes on current ownership
### Java owns most visible product behavior
Use Java app for:
- dashboard work
- auth
- public pages
- survey UI
- payment flow
- live-help UI flow

### Python owns AI/runtime behavior
Use Python service for:
- AI qualifier logic
- runtime bridge behavior
- transitional support paths still called by Java

## 9. Legacy stack note
The following still exist but are not the main local path anymore:
- `frontend/ACE-Chatbot/`
- `frontend/manager-dashboard/`
- `portal/portal/`
- full compose flows that assume Angular is the main frontend

Keep them only for legacy/reference work until repo cleanup is complete.
