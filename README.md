# ACE Reception Services

AI receptionist platform for Slovenian beauty salons — a digital front desk. Chat-based AI that greets visitors, answers questions about services, books appointments, and hands off to human staff via live video.

## Quick Start

```bash
# 1. Start infrastructure
docker compose -f docker-compose-simple.yml up -d

# 2. Start backend (Python)
cd backend && source ../venv/bin/activate
uvicorn main:app --port 8000 --reload

# 3. Open in browser
open http://localhost:8000
```

On first run, auto-seeds: demo org, admin user (`admin` / `test123`), AI Receptor qualifier.

## Stack

| Layer | Tech | Lines |
|---|---|---|
| Backend | Python FastAPI (`backend/`) | ~662 |
| AI | LangGraph + OpenAI (`app/`) | ~550 |
| Frontend | Angular 19 SPA (`angular-visitor/`) | ~1200 |
| Database | PostgreSQL 15 | — |
| Video | LiveKit (self-hosted) | — |

**One Python process.** No Java, no microservices. The backend serves the SPA as static files.

## Key Features

- **AI receptionist chat** — Slovenian, warm, professional tone
- **3 beauty services** — Nega obraza (45min/35€), Maska obraza (30min/25€), Čiščenje obraza (60min/50€)
- **Appointment booking** — Calendar picker with available slots
- **Staff takeover** — Human joins conversation with live video fade-in
- **Camera handoff** — One-way LiveKit video (staff publishes, visitor views)
- **Multi-tenant** — Organizations with configurable AI qualifiers

## Documentation

- **[CONTEXT.md](CONTEXT.md)** — Complete project overview for LLMs and developers. Architecture, data model, API surface, AI flow, all file purposes.
- **[Reception-Services.txt](Reception-Services.txt)** — Project goal and product vision
- **[docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md)** — Local dev runbook
- **[docs/VIDEO_TAKEOVER_SPEC.md](docs/VIDEO_TAKEOVER_SPEC.md)** — Camera takeover design
- **[docs/AI_QUALIFIER_SPEC.md](docs/AI_QUALIFIER_SPEC.md)** — Qualifier system design
- **[docs/EVENTS.md](docs/EVENTS.md)** — Event contracts
- **[docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md)** — Data model contracts

## API at a Glance

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /chat` | No | Visitor sends message → AI reply |
| `POST /login` | No | Form login → JWT |
| `GET /chat-events/poll` | No | Real-time event polling |
| `GET /api/public/organizations/{slug}/live-session` | No | Check camera live status |
| `POST /chat/staff` | JWT | Staff takeover message |
| `POST /api/organizations/{id}/live-sessions/go-live` | JWT | Start camera session |
| `POST /api/organizations/{id}/live-sessions/end` | JWT | End camera session |
