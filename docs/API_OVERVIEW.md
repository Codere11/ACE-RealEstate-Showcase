# API Overview

ACE e-Counter has two important server surfaces:

- **Java app** on `http://localhost:8080` — primary product routes
- **Python service** on `http://localhost:8000` — AI/runtime routes

## Java app (`java-platform/`)
Main user-facing and manager-facing routes live here.

### Key routes
- `/login`
- `/{orgSlug}`
- `/{orgSlug}/survey/{surveySlug}`
- `/{orgSlug}/dashboard`
- `/admin/dashboard`
- `/actuator/health`

### Java-owned API routes
Representative current Java routes:
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

## Python service (`app/`)
The Python service provides AI/runtime support.

### Key routes
- `/chat/*`
- `/chat-events/*`
- `/api/public/organizations/{orgSlug}/qualifier-active`
- `/api/public/organizations/{orgSlug}/live-session`
- supporting runtime/internal routes used by the Java app

### Runtime docs
- `http://localhost:8000/docs`

## Ownership summary
### Use Java code for
- dashboard UX
- public site UX
- surveys and qualifier management UI
- auth
- payment flow
- live-help UI/session flow

### Use Python code for
- AI qualifier logic
- runtime conversation behavior
- event/runtime support paths

## Useful local URLs
- Java app: `http://127.0.0.1:8080`
- Java health: `http://127.0.0.1:8080/actuator/health`
- Python docs: `http://127.0.0.1:8000/docs`
