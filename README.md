<!-- Created: 2026-03-14T20:44:39Z -->
# ACE Real Estate
A multi-tenant lead qualification platform for real-estate teams.  
This project demonstrates end-to-end product engineering: backend architecture, multi-app frontend setup, event-driven handoff, and containerized local deployment.
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-Frontend-DD0031?logo=angular&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Local%20Stack-2496ED?logo=docker&logoColor=white)

## Problem
Real-estate teams lose time and revenue when inbound leads are qualified manually and followed up too late.

## Solution
ACE Real Estate automates intake, qualification, and routing:
- Customer-facing chatbot/survey collects lead data
- Backend scores and stores leads
- Manager dashboard gets real-time high-value lead signals
- Admin portal manages tenant-specific configuration

## Tech Stack
- Backend: Python, FastAPI
- Frontend: Angular (3 separate applications)
- Database: PostgreSQL
- Runtime: Docker Compose
- Core patterns: multi-tenancy, role-based APIs, configuration-driven flow logic, event/WebSocket handoff

## System Components
- `frontend/ACE-Chatbot` — customer-facing lead intake UI
- `frontend/manager-dashboard` — operator/manager dashboard
- `portal/portal` — admin portal
- `app/` — API, services, auth, orchestration
- `data/` — conversation flow/configuration files

## Quick Start (recommended)
Use the simplified compose setup for local development:

1. Create env file:
   ```bash
   cp .env.example .env
   ```
2. Start services:
   ```bash
   docker compose -f docker-compose-simple.yml up -d --build
   ```
3. Open applications:
   - Chatbot UI: `http://localhost:4200`
   - Manager dashboard: `http://localhost:4400`
   - Admin portal: `http://localhost:4500`
   - API docs: `http://localhost:8000/docs`

## Product Demo
### 1) Survey Intake
![Survey intake screen](docs/media/chatbot-survey-screen.png)
User starts with a short property questionnaire to capture intent and preferences.

### 2) Chat Follow-up
![Chat follow-up screen](docs/media/chatbot-chat-screen.png)
After intake, the flow moves into chat for qualification and next-step coordination.

### 3) Manager Dashboard
![Manager dashboard screen](docs/media/dashboard-leads-screen.png)
Lead responses are visible in the dashboard for filtering, prioritization, and takeover.

### 4) Screencast (1 minute)
- [Watch product walkthrough video (WebM)](docs/media/ace-demo-1min.webm)

## What This Project Demonstrates
- Building and shipping a multi-app product, not just isolated scripts
- Designing a multi-tenant backend with role-specific interfaces
- Implementing event-driven handoff from intake to operator workflows
- Running reproducible full-stack local environments with Docker

## Engineering Highlights
- Multi-tenant architecture with per-tenant isolation and configurable flows
- Node-based conversation logic with AI-assisted scoring support
- Real-time lead escalation to operators
- Modular service-oriented backend structure
- Fully containerized local stack for reproducibility

## Documentation
- Architecture diagrams: `ARCHITECTURE.md`
- Local setup and runbook: `docs/LOCAL_DEVELOPMENT.md`
- API route map: `docs/API_OVERVIEW.md`
- Recruiter/product presentation guide: `docs/PROJECT_PRESENTATION.md`
- GitHub launch pack (profile + pinned repo text): `docs/GITHUB_LAUNCH_PACK.md`
- Archived legacy docs: `docs/archive/README.md`

## Repository Map
- `app/` — FastAPI routers, services, auth, portal routes, middleware
- `frontend/ACE-Chatbot/` — intake/chat UI
- `frontend/manager-dashboard/` — manager UI
- `portal/portal/` — admin UI
- `scripts/` — operational scripts and helpers
- `static/` — static assets

## Notes
- Keep secrets out of git (`.env` is local-only)
- Use `.env.example` as the template
- Prefer `docker-compose-simple.yml` for onboarding and demos
