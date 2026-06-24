# ACE

AI SDR that qualifies website visitors and books instant video meetings with your sales team.

## What it does

1. Visitor lands on your site → ACE greets them in chat
2. Qualifies in 2-3 turns: who are you, what's your budget, what problem are you solving
3. Offers instant live video meeting with your sales team
4. After the meeting, salesperson types quick notes → ACE formats them into a lead card

## Quick Start

```bash
docker compose -f docker-compose-simple.yml up -d
open http://localhost:8000
```

Auto-seeds demo org. Login: `admin` / `test123`

| URL | What |
|---|---|
| `/demo` | Visitor chatbot |
| `/demo/dashboard` | Staff dashboard |
| `/login` | Login page |

## Stack

Python FastAPI + Angular 19 + PostgreSQL + LiveKit. One process, no microservices.

## Features

- AI chat qualification
- Instant video handoff (LiveKit, two-way)
- Lead cards with extracted profile (name, phone, email, budget, problem)
- Meeting notes: type shorthand, AI formats into summary
- Staff dashboard with conversation threads, booking timeline, lead cards

## Docs

- **[CONTEXT.md](CONTEXT.md)** — Full architecture, data model, API, AI flow
- **[Startup.txt](Startup.txt)** — Runbook
- **[docs/](docs/)** — Additional specs
