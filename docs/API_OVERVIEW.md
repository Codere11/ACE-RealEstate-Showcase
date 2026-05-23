# API Overview

ACE Reception Services has three server surfaces:

- **Angular SPA** on `http://localhost:4200` — visitor-side receptionist experience (planned)
- **Java app** on `http://localhost:8080` — backend API + manager dashboard
- **Python service** on `http://localhost:8000` — AI/runtime routes

## Angular visitor SPA (`angular-visitor/` — planned)
The visitor-facing single-page application. Talks to the Java REST API and LiveKit directly.

### Key capabilities
- AI receptionist chat widget
- Service browsing (3 demo services with photos)
- Calendar / appointment booking
- Open/closed hours live indicator
- LiveKit video handoff (staff fade-in)
- Accept/deny/request-human controls

## Java app (`java-platform/`)
Backend REST API for the Angular SPA, plus Thymeleaf-rendered manager dashboard.

### Key routes
- `/login`
- `/{orgSlug}/dashboard` — manager dashboard (Thymeleaf SSR)
- `/admin/dashboard`
- `/actuator/health`

### Java-owned API routes (REST — consumed by Angular SPA)
- `/api/organizations/{orgId}/config` — org settings, services, hours
- `/api/organizations/{orgId}/leads`
- `/api/organizations/{orgId}/leads/{sid}/messages`
- `/api/organizations/{orgId}/services` — beauty services
- `/api/organizations/{orgId}/appointments` — calendar / booking
- `/api/organizations/{orgId}/live-sessions/*`
- `/api/public/organizations/{orgSlug}/status` — open/closed, services

## Python service (`app/`)
The Python service provides AI receptionist behavior.

### Key routes
- `/chat/*` — conversational AI receptionist
- `/chat-events/*`
- `/api/public/organizations/{orgSlug}/receptionist-active`
- `/api/public/organizations/{orgSlug}/live-session`
- supporting runtime/internal routes used by the Java app

### Runtime docs
- `http://localhost:8000/docs`

## Ownership summary
### Use Angular for
- visitor-side AI receptionist UX
- service browsing and presentation
- calendar and booking UI
- live video handoff experience

### Use Java code for
- REST API for the Angular SPA
- dashboard UX (Thymeleaf SSR)
- auth
- org and service management
- live-session orchestration
- calendar/appointment backend

### Use Python code for
- AI receptionist conversational logic
- LangGraph-based intent routing
- runtime conversation behavior
- event/runtime support paths

## Useful local URLs
- Angular visitor: `http://127.0.0.1:4200`
- Java app: `http://127.0.0.1:8080`
- Java health: `http://127.0.0.1:8080/actuator/health`
- Python docs: `http://127.0.0.1:8000/docs`
