# ACE Reception Services

ACE Reception Services is an **AI receptionist platform for Slovenian beauty salons (kozmeticni saloni)** — a no-brainer for any salon looking to modernize their front desk.

It replicates the real-world reception experience online: greet visitors, answer questions, help them select services, book appointments, and hand off to human staff when needed.

## Goal

> Make ACE a **no-brainer** for Slovenian beauty salons and similar appointment-based service businesses.

Why salons: they already have the perfect business model to digitalize — someone walks in, talks with the receptionist, asks questions, selects a service, gets it done. Higher transaction volume = faster revenue via commissions.

## Demo concept
- **3 demo services** with AI-generated photos
- **AI receptionist** sits middle-bottom of the page — highly inviting
- **"We are open — a human can join you"** / **"We are closed — I can handle the basics"**
- **Calendar + appointment booking** on the visitor side
- **Live staff video handoff** with slow fade-in (accept/deny controls)
- **Staff dashboard** with calendar, leads, and conversation takeover

## Stack
- **Angular** — visitor-side SPA (AI receptionist chat, services, calendar, live handoff)
- **Java 21 + Spring Boot + Thymeleaf** — backend REST API + manager dashboard
- **Python + FastAPI + LangGraph** — AI/runtime service and receptionist orchestration
- **PostgreSQL** — persistence
- **LiveKit** — live staff video handoff

## What lives where
- `angular-visitor/` — visitor-side Angular SPA (planned)
- `java-platform/` — backend API + manager dashboard
- `app/` — Python AI/runtime service
- `ace-mobile/` — existing Ionic/Angular mobile companion
- `docs/` — product and architecture documentation
- `scripts/` — helper and seed scripts

## Product surface
### Visitor side (Angular SPA)
Visitors can:
- chat with the AI receptionist naturally
- browse services with AI-generated photos
- get answers about services, pricing, and availability
- book appointments via calendar
- see open/closed hours status
- accept or deny staff joining the conversation
- explicitly request a human staff member
- experience a premium slow fade-in when staff joins via video

### Manager side (Java dashboard)
Managers can:
- manage calendar and appointments
- inspect lead threads and conversation history
- take over conversations from the AI receptionist
- join visitor conversations via live video
- manage services and operating hours
- set open/closed status

## Architecture summary
### Angular visitor SPA
The visitor experience — the core product surface. An AI receptionist that feels like walking into a real salon.

### Java app
Backend REST API serving the Angular SPA, plus the Thymeleaf-rendered manager dashboard. Owns auth, org management, calendar, leads, and live-session orchestration.

### Python service
The AI brain — LangGraph-powered receptionist logic, intent routing (greet → qualify → book → handoff), and conversational behavior.

## Live deployment shape
The live Railway deployment runs as a **single public container** built from the repo-root `Dockerfile`:
- Java serves the API + dashboard on the external port
- Python runtime runs inside the same container on `127.0.0.1:8000`
- Angular visitor SPA is served as static assets (or via separate deployment)
- PostgreSQL remains a separate managed Railway service

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

### 3. Run the Python AI/runtime service
```bash
./run_backend.sh
```

### 4. Run the Angular visitor SPA (planned)
```bash
cd angular-visitor
ng serve
```

### Main local URLs
- Angular visitor: `http://127.0.0.1:4200`
- Java app: `http://127.0.0.1:8080`
- Demo dashboard: `http://127.0.0.1:8080/demo/dashboard`
- Login: `http://127.0.0.1:8080/login`
- Demo credentials: `admin / test123`
- Python service docs: `http://127.0.0.1:8000/docs`

## Documentation
- `Reception-Services.txt` — project goal and north star
- `ARCHITECTURE.md` — system architecture with flow diagrams
- `docs/PRODUCT_OVERVIEW.md` — product-level overview
- `docs/LOCAL_DEVELOPMENT.md` — local runbook
- `docs/API_OVERVIEW.md` — route ownership summary

## Author
Maks Ponikvar

## Contact
- Email: `maks.ponikvar@gmail.com`
- GitHub: `https://github.com/Codere11`
