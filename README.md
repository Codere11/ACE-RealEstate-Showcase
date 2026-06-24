# ACE

AI SDR that qualifies B2B website visitors and books insta-meetings with your sales team.

## What ACE Does

A chat widget that lives on your B2B website. An AI agent greets visitors, qualifies them in 2-3 turns, and pushes for an **instant live takeover** by your sales team — or schedules a discovery call for later.

```
Visitor lands on your site
  → ACE greets, asks what they need
  → Qualifies: budget? problem? timeline?
  → "Bi želeli da se naša ekipa TAKOJ vključi v pogovor?"
  → Sales guy joins live chat (text + optional video via LiveKit)
  → Or: discovery call scheduled for tomorrow at 10:00
```

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

On first run, auto-seeds: demo org, admin user (`admin` / `test123`), AI Svetovalec qualifier.

## Stack

| Layer | Tech | Lines |
|---|---|---|
| Backend | Python FastAPI (`backend/`) | ~700 |
| AI | LangGraph + OpenAI (`app/`) | ~550 |
| Frontend | Angular 19 SPA (`angular-visitor/`) | ~1,200 |
| Database | PostgreSQL 15 | — |
| Video | LiveKit (self-hosted) | — |

**One Python process.** No Java, no microservices. The backend serves the SPA as static files.

## Key Features

- **AI qualification chat** — Slovenian, direct, business-focused tone
- **Instant team takeover** — AI pushes for live handoff on turn 1 if lead is qualified
- **Discovery call scheduling** — Calendar booking for later calls when team is offline
- **Live video** — One-way LiveKit video (sales publishes, visitor views)
- **Lead profiling** — Extracts business_name, budget, problem, company_type from conversation
- **Staff dashboard** — Lead list with threads, takeover controls, booking timeline
- **Multi-tenant** — Per-company organizations with configurable AI qualifiers
- **Analytics engine** — AI-powered business intelligence that labels conversations and finds funnel leaks

## Documentation

- **[CONTEXT.md](CONTEXT.md)** — Complete project overview: architecture, data model, API, AI flow
- **[Startup.txt](Startup.txt)** — Runbook: Docker, local dev, endpoints
- **[WARP.md](WARP.md)** — Quick reference: commands, URLs, architecture
- **[docs/AI_QUALIFIER_SPEC.md](docs/AI_QUALIFIER_SPEC.md)** — Qualifier system design
- **[docs/VIDEO_TAKEOVER_SPEC.md](docs/VIDEO_TAKEOVER_SPEC.md)** — Camera takeover design
- **[docs/EVENTS.md](docs/EVENTS.md)** — Event contracts
- **[docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md)** — Data model

## API at a Glance

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /chat` | No | Visitor sends message → AI reply |
| `POST /chat/stream` | No | Streaming version (SSE) |
| `POST /login` | No | Form login → JWT |
| `GET /chat-events/poll` | No | Real-time event polling |
| `POST /chat/staff` | JWT | Staff takeover message |
| `GET /api/organizations/{id}/leads` | JWT | List leads with scores, profiles |
| `POST /api/organizations/{id}/live-sessions/go-live` | JWT | Start video session |
| `POST /api/organizations/{id}/live-sessions/end` | JWT | End video session |
