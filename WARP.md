# WARP.md

ACE Reception Services — AI receptionist for Slovenian beauty salons.

This repository is centered on:
- `angular-visitor/` — Angular SPA (visitor-side receptionist, planned)
- `java-platform/` — Spring Boot backend API + manager dashboard
- `app/` — Python FastAPI + LangGraph AI/runtime service

## Common commands

### Angular visitor SPA (planned)
```bash
cd angular-visitor
ng serve
```

### Java app
```bash
cd java-platform
./mvnw spring-boot:run
./mvnw test -q
```

### Python service
```bash
./run_backend.sh
```

### Infra
```bash
docker compose -f docker-compose-simple.yml up -d
```

## Local URLs
- Angular visitor: `http://127.0.0.1:4200`
- Java app: `http://127.0.0.1:8080`
- Python docs: `http://127.0.0.1:8000/docs`

## Architecture note
Angular SPA = visitor product surface (AI receptionist, services, booking, live handoff).
Java app = REST API for Angular + Thymeleaf dashboard for managers.
Python service = AI receptionist brain (LangGraph intent routing).
