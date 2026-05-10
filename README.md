# ACE e-Counter

ACE e-Counter is a multi-tenant visitor-intake and conversion platform built around a **Java Spring Boot application** with a supporting **Python AI/runtime service**.

It is designed to show a complete product story:
- visitor intake through survey or open chat
- AI-assisted qualification
- manager-side lead operations
- live human handoff
- payment request flow with Stripe-hosted checkout

## Stack
- **Java 21 + Spring Boot + Thymeleaf** — main product application
- **Python + FastAPI + LangGraph** — AI/runtime service and qualification orchestration
- **PostgreSQL** — persistence
- **LiveKit** — live-help transport for demo/testing
- **Stripe / Stripe Connect** — payment requests and hosted checkout

## What lives where
- `java-platform/` — primary application
- `app/` — Python AI/runtime service
- `docs/` — product and architecture documentation
- `scripts/` — helper and seed scripts

## Product surface
### Visitor side
Visitors can:
- start in survey mode or open qualification chat
- continue the conversation naturally
- receive live human help when a manager steps in
- receive a payment request button directly in chat

### Manager side
Managers can:
- open the organization dashboard
- inspect lead threads and qualification signals
- take over chat
- manage surveys and qualifier behavior
- preview and start live help
- send payment requests

## Architecture summary
### Java app
The Java application is the main user-facing product.
It currently owns:
- auth and login
- public visitor routes
- organization dashboard
- survey management UI
- qualifier management UI
- lead thread and takeover flow
- live-help session UI flow
- payment request UI and public payment pages

### Python service
The Python service supports AI/runtime behavior, including:
- qualifier/runtime logic
- LangGraph-based qualification orchestration
- event and runtime support paths
- integration points used by the Java app when AI behavior is needed

## Local development
### 1. Start infrastructure
```bash
docker compose -f docker-compose-simple.yml up -d
```

### 2. Run the Java app
```bash
cd java-platform
./mvnw spring-boot:run
```

### 3. Optionally run the Python AI/runtime service
```bash
./run_backend.sh
```

### Main local URLs
- Java app: `http://127.0.0.1:8080`
- Demo public route: `http://127.0.0.1:8080/demo`
- Demo dashboard: `http://127.0.0.1:8080/demo/dashboard`
- Login: `http://127.0.0.1:8080/login`
- Demo credentials: `admin / test123`
- Python service docs: `http://127.0.0.1:8000/docs`

## Documentation
- `ARCHITECTURE.md` — current system architecture
- `docs/LOCAL_DEVELOPMENT.md` — Java-first local runbook
- `docs/PRODUCT_OVERVIEW.md` — product-level overview
- `docs/API_OVERVIEW.md` — Java and Python route ownership summary
- `docs/AI_QUALIFIER_SPEC.md` — qualifier/product behavior details
- `docs/LIVE_HELP_SPEC.md` — live-help design notes
- `docs/STRIPE_CONNECT_LOCAL_SETUP.md` — Stripe local setup notes

## Why this repo is strong
ACE e-Counter shows:
- product architecture, not isolated scripts
- a clean Java app paired with a focused Python AI service
- multi-tenant design
- manager-side operational workflows
- a real path from intake to conversion

## Author
Maks Ponikvar

## Contact
- Email: `maks.ponikvar@gmail.com`
- GitHub: `https://github.com/Codere11`
