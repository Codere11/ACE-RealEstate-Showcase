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
- `/api/organizations/{org_id}/qualifiers/*` — tenant AI qualifier CRUD, publish/archive, lead-profile reads
- `/api/organizations/{org_id}/payment-settings/*` — tenant Stripe Connect/payment configuration state
- `/api/organizations/{org_id}/payment-requests/*` — tenant payment request creation/listing
- `/api/public/organizations/{org_slug}/qualifier-active` — public live-qualifier check for chatbot entry mode
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

## Qualifier Runtime Notes
- `/chat/` now returns open chat mode when a live qualifier is active for the organization
- chat responses can include qualifier metadata such as band, confidence, reasoning, and takeover flags
- the active qualifier path currently runs a lightweight LangGraph-style flow: `extract -> score -> reply`

## Payments / Stripe Connect Notes
- Stripe Connect is configured at the **organization** level, not per lead
- local platform setup may require `.env`, but tenant/business-owner setup should be only a dashboard **Connect Stripe** action
- payment requests can currently resolve to:
  - connected-account Stripe Checkout when the org account is fully ready
  - platform Stripe-hosted demo checkout when the connected account is still restricted
- public routes include Stripe callback/webhook/payment pages:
  - `/api/public/payments/stripe/connect/callback`
  - `/api/payments/webhooks/stripe`
  - `/pay/{public_token}`
  - `/pay/success`
  - `/pay/cancel`

## API Docs
- Swagger/OpenAPI: `http://localhost:8000/docs`

For exact request/response contracts, use the generated OpenAPI docs at runtime.
