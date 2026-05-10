# API Overview

This repo currently has **two important server surfaces**:

- **Java app** on `http://localhost:8080` — primary product web app and most current routes
- **Python service** on `http://localhost:8000` — AI/runtime service and some legacy/transitional APIs

Do not think of the system as “Python backend with Angular frontend” anymore.
That is old repo history, not the current truth.

## 1. Java app surface (`java-platform/`)
Main user-facing and manager-facing routes now live here.

### Main routes
- `/login` — login
- `/{orgSlug}` — public organization route
- `/{orgSlug}/survey/{surveySlug}` — public survey route
- `/{orgSlug}/dashboard` — organization dashboard
- `/admin/dashboard` — platform admin/dashboard surface
- `/actuator/health` — health check

### Manager/API routes in Java
Representative current Java-owned routes:
- `/api/organizations/{orgId}/leads`
- `/api/organizations/{orgId}/leads/{sid}/messages`
- `/api/organizations/{orgId}/surveys/*`
- `/api/organizations/{orgId}/qualifiers/*`
- `/api/organizations/{orgId}/live-sessions/*`
- `/api/organizations/{orgId}/payment-settings/*`
- `/api/organizations/{orgId}/payment-requests/*`
- `/api/public/payments/stripe/connect/callback`
- `/api/payments/webhooks/stripe`
- `/pay/{publicToken}`
- `/pay/success`
- `/pay/cancel`

## 2. Python service surface (`app/`)
Python is now mainly the AI/runtime side plus transitional support.

Base local URL:
- `http://localhost:8000`

Representative routes still important there:
- `/chat/*` — runtime chat path
- `/chat-events/*` — event polling/stream paths
- `/api/public/organizations/{orgSlug}/qualifier-active`
- `/api/public/organizations/{orgSlug}/live-session`
- supporting runtime/internal routes used by Java or legacy flows

OpenAPI docs:
- `http://localhost:8000/docs`

## 3. Ownership summary
### Java owns most current product behavior
Use Java code when working on:
- dashboard UX
- public site UX
- surveys and qualifier management UI
- auth
- payment UI and payment request flow
- current live-help UI/session flow

### Python owns AI/runtime behavior
Use Python code when working on:
- AI qualifier logic
- runtime conversation behavior
- event/runtime support paths
- transitional integrations not yet pulled into Java

## 4. Legacy note
The repo still contains older Angular frontends and some Python-first API assumptions in docs/code.
Those should be treated as **legacy/transitional**, not as the main architectural truth.

## 5. Local URLs worth remembering
- Java app: `http://127.0.0.1:8080`
- Java health: `http://127.0.0.1:8080/actuator/health`
- Python service docs: `http://127.0.0.1:8000/docs`

For exact request/response contracts, inspect the code directly or use runtime docs where available.
