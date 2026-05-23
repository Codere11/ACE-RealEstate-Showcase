# Local Development Runbook

This is the recommended local path for the current ACE Reception Services architecture.

## Prerequisites
- Java 21
- Python 3
- Docker + Docker Compose v2

## 1. Environment
The Java app imports `.env` automatically.
The Python service also uses it.

If needed:
```bash
cp .env.example .env
```

Important variables:
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

## 2. Start infrastructure
```bash
docker compose -f docker-compose-simple.yml up -d
```

This starts:
- PostgreSQL on `localhost:5433`
- LiveKit for local live-help testing

## 3. Run the Java app
```bash
cd java-platform
./mvnw spring-boot:run
```

Health check:
```bash
curl -sf http://127.0.0.1:8080/actuator/health
```

## 4. Optionally run the Python AI/runtime service
Use this when working on qualifier/runtime behavior.

```bash
cd /home/maksich/Documents/ACE-RealEstate
./run_backend.sh
```

Python docs:
- `http://127.0.0.1:8000/docs`

## 5. Useful routes
### Java app
- Home: `http://127.0.0.1:8080/`
- Demo public route: `http://127.0.0.1:8080/demo`
- Demo dashboard: `http://127.0.0.1:8080/demo/dashboard`
- Login: `http://127.0.0.1:8080/login`
- Demo credentials: `admin / test123`

### Python service
- Docs: `http://127.0.0.1:8000/docs`

## 6. Tests
### Java
```bash
cd java-platform
./mvnw test -q
```

### Python
Run when working in `app/`.

## 7. Notes
- Java owns the main product surface
- Python provides AI/runtime support
- PostgreSQL is shared
- Stripe and LiveKit are available for local demo/testing flows
