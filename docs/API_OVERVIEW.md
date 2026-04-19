<!-- Created: 2026-04-18T12:20:22Z -->
# API Overview
High-level route map for ACE Real Estate backend (`app/main.py`).

Base URL (local): `http://localhost:8000`

## Core Routes
- `/chat/*` — chat and conversation operations
- `/chats/*` — chat history and chat list reads
- `/leads/*` — lead creation and management
- `/kpis/*` — KPI aggregation endpoints
- `/funnel/*` — funnel metrics and reporting
- `/objections/*` — objection tracking/analytics
- `/agent/*` — agent-specific backend flows
- `/chat-events/*` — event stream endpoints (separated from `/chat`)
- `/health/*` — health and service checks

## Survey and Flow Routes
- Survey flow management routes are registered without a static prefix (see `survey_flow.router`)
- Public survey access includes slug-based endpoints via `public_survey.router`

## Auth and Access Control
- `/api/auth/*` — authentication routes
- `/api/admin/*` — admin APIs
- `/api/manager/*` — manager APIs

## Multi-Tenant API Surface
- `/api/organizations/*` — organization lifecycle
- `/api/organizations/{org_id}/users/*` — tenant user management
- `/api/organizations/{org_id}/surveys/*` — tenant survey management
- `/api/organizations/{slug}/avatar/*` — organization avatar endpoints
- `/api/users/me/avatar/*` — authenticated user avatar endpoints

## Static and Instance Mounts
- `/static/*` — static files
- `/instances/{slug}/chatbot/*` — mounted tenant chatbot UIs

## CORS Notes
Local origins allowed include:
- `localhost:4200` (chatbot)
- `localhost:4400` (manager dashboard)
- `localhost:4500` (admin portal)
- mobile/capacitor local origins

## API Docs
- Swagger/OpenAPI: `http://localhost:8000/docs`

For exact request/response contracts, use the generated OpenAPI docs at runtime.
