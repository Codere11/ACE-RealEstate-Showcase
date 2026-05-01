<!-- Created: 2026-03-14T20:44:39Z -->
# ACE Real Estate
A multi-tenant real-estate lead qualification platform with a customer chatbot, manager dashboard, and tenant-aware backend.

This project is meant to show **product engineering**, not just isolated AI or frontend experiments:
- manager-configured AI qualification
- real-time dashboard visibility
- event-driven handoff between chat and operators
- payment request workflow with a Stripe Connect path
- Dockerized full-stack local setup

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-Frontend-DD0031?logo=angular&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Local%20Stack-2496ED?logo=docker&logoColor=white)

## The Problem
Real-estate teams lose time and revenue when inbound leads are:
- qualified manually
- followed up too late
- handled in disconnected tools
- escalated without clear lead quality or next-step context

A normal website form or rigid survey also creates friction too early.

## The Solution
ACE Real Estate combines a conversational intake layer with manager-side control.

### Visitor side
- start with either a survey or open chat, depending on tenant configuration
- ask questions naturally
- get qualified in the background without being forced through a long form
- receive a payment request when the manager decides the lead is ready

### Manager side
- configure the AI qualifier per organization
- see evolving lead quality, confidence, reasoning, and takeover eligibility
- step into the conversation when needed
- send a payment request directly from the dashboard

## Why each major piece exists
### 1. Customer chatbot
Exists to reduce friction at the top of the funnel.

It supports:
- survey mode when structured intake is appropriate
- open AI qualification mode when a live qualifier exists
- payment request cards inside the chat flow

### 2. AI qualifier
Exists to make qualification configurable and useful instead of hardcoded.

It gives the manager:
- structured lead profile updates
- deterministic scoring and banding
- confidence and reasoning
- takeover/video eligibility signals

### 3. Manager dashboard
Exists to make the system operational, not just conversational.

It lets the team:
- review leads in real time
- inspect lead profile quality
- manage qualifier behavior
- send payment requests
- take over the conversation when needed

### 4. Event-driven backend
Exists so the product behaves like a live system, not a static form app.

It is used for:
- chat updates
- lead qualification updates
- payment request state updates
- manager/dashboard synchronization

### 5. Payment request flow
Exists because qualification should lead to a real business action.

The manager can:
- create a payment request for a lead
- send it directly into chat
- open a hosted checkout flow
- track paid/sent status

## Current demoable flow
The project is currently coherent enough to demo this end-to-end story:

1. visitor opens chatbot
2. tenant-specific qualifier runs in free-text mode
3. manager sees lead quality in dashboard
4. manager sends a payment request
5. visitor opens a Stripe-hosted checkout
6. payment state updates back into the system

## Product Demo
### 1) Survey Intake
![Survey intake screen](docs/media/chatbot-survey-screen.png)
User can still start with a short property questionnaire when no active AI qualifier is configured.

### 2) Open AI Qualification Chat
![Chat follow-up screen](docs/media/chatbot-chat-screen.png)
When an organization has a live qualifier, the chatbot starts directly in free-text mode and qualifies the lead conversationally.

### 3) Manager Dashboard
![Manager dashboard screen](docs/media/dashboard-leads-screen.png)
Managers can configure qualifiers, inspect lead quality, and send payment requests.

### 4) Screencast
- [Watch product walkthrough video (WebM)](docs/media/ace-demo-1min.webm)

## Current implementation status
### Implemented now
- multi-tenant organizations, users, surveys, qualifiers, and lead profiles
- manager-driven AI qualifier resource with CRUD + publish/archive flow
- qualifier runtime with `extract -> score -> reply`
- live qualifier-aware chatbot entry mode
- dashboard lead visibility for score, confidence, reasoning, takeover/video flags
- payment request flow in dashboard + chatbot
- Stripe Connect architecture path at organization level
- Stripe-hosted checkout path
- local Stripe demo fallback when connected account is not fully payment-ready yet
- Dockerized local stack

### Intentionally not finished yet
- grounded listing/retrieval answers
- final video takeover flow
- polished production-ready Stripe Connect onboarding for real clients
- deeper analytics/reporting

## Architecture at a glance
### Backend
- **FastAPI** for APIs and orchestration
- **SQLAlchemy + PostgreSQL** for tenant-scoped persistence
- event bus + long-poll/SSE-style updates for live UI synchronization

### Frontend
- **Angular chatbot** for visitor intake and conversational UI
- **Angular manager dashboard** for lead operations, qualifier management, and payments
- **Portal/admin app** for additional management concerns

### Runtime patterns
- multi-tenancy
- role-based access
- DB-backed configuration
- event-driven updates
- hosted third-party checkout instead of hand-rolled payment UI

## Why this project is technically interesting
This is not just “a chatbot project.”
It demonstrates:
- multi-app product architecture
- tenant-scoped configuration and runtime behavior
- AI-assisted but controlled orchestration
- structured data persistence behind chat interactions
- dashboard/operator workflows
- payment workflow integration
- full-stack local reproducibility with Docker

## Quick Start
Use the simplified compose setup for local development:

```bash
cp .env.example .env
docker compose -f docker-compose-simple.yml up -d --build
```

Open:
- Chatbot UI: `http://localhost:4200`
- Manager dashboard: `http://localhost:4400`
- Admin portal: `http://localhost:4500`
- API docs: `http://localhost:8000/docs`

Useful demo routes:
- Demo chatbot org route: `http://localhost:4200/demo-agency/nepremicnine`
- Manager login: `http://localhost:4400/login`
- Demo manager credentials: `admin / test123`

## Documentation
### Start here
- Product overview: `docs/PRODUCT_OVERVIEW.md`
- Local setup: `docs/LOCAL_DEVELOPMENT.md`
- API route overview: `docs/API_OVERVIEW.md`

### Core feature docs
- AI qualifier spec: `docs/AI_QUALIFIER_SPEC.md`
- Data contracts: `docs/DATA_CONTRACTS.md`
- Live events: `docs/EVENTS.md`
- Stripe Connect local setup: `docs/STRIPE_CONNECT_LOCAL_SETUP.md`
- Video takeover spec: `docs/VIDEO_TAKEOVER_SPEC.md`

### Additional docs
- Architecture diagrams: `ARCHITECTURE.md`
- Recruiter/product presentation guide: `docs/PROJECT_PRESENTATION.md`
- GitHub launch pack: `docs/GITHUB_LAUNCH_PACK.md`
- Archived legacy docs: `docs/archive/README.md`

## Repository Map
- `app/` — FastAPI routers, services, auth, middleware, orchestration
- `frontend/ACE-Chatbot/` — visitor-facing intake/chat UI
- `frontend/manager-dashboard/` — manager/operator dashboard
- `portal/portal/` — admin UI
- `scripts/` — helper/seed scripts
- `docs/` — focused architecture/product documentation

## Notes
- Keep secrets out of git (`.env` is local-only)
- Use `.env.example` as the template
- Prefer `docker-compose-simple.yml` for onboarding and demos
- For local Stripe Connect testing, expose the backend publicly and keep dashboard/chatbot local

## Author
Maks Ponikvar

## Contact
- Email: `maks.ponikvar@gmail.com`
- GitHub: `https://github.com/Codere11`
