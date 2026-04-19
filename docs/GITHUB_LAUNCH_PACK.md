<!-- Created: 2026-04-18T12:20:22Z -->
# GitHub Launch Pack
Use this to present ACE Real Estate as your flagship repository.

## 1) Suggested GitHub Bio
`Junior Python/Backend developer building production-style SaaS systems with FastAPI, PostgreSQL, Docker, and Angular.`

## 2) Suggested Pinned Repositories (order)
1. `ACE-RealEstate` (flagship, this project)
2. A second backend/data project with clear scope
3. A smaller utility/tooling repo showing clean code and tests

If you have mostly old/noisy repos, make them private or archive them and pin only the strongest ones.

## 3) Repo Description (copy-ready)
`Multi-tenant lead qualification platform (FastAPI + Angular + PostgreSQL) with real-time operator handoff and Dockerized local stack.`

## 4) Short Project Summary for Applications
`Built a multi-tenant lead qualification platform with FastAPI, PostgreSQL, and Angular. Implemented conversation-driven lead intake, backend scoring workflows, and real-time handoff to a manager dashboard. Containerized full local deployment with Docker Compose.`

## 5) README Media Checklist
Add these files before sharing publicly:
- `docs/media/chatbot-intake.png`
- `docs/media/manager-dashboard.png`
- `docs/media/admin-portal.png`
- `docs/media/ace-demo.gif`

## 6) One-Command Publish (new repo)
After committing your local changes, run:

```bash
./scripts/publish_new_repo.sh ACE-RealEstate-Showcase --public
```

This script will:
- create a new GitHub repo via `gh`
- set/update `origin`
- push your current branch

## 7) Final Quality Gate Before Sending Applications
- README opens with clear problem/solution and stack
- Quickstart works from a clean machine
- API docs are reachable at `:8000/docs`
- Screenshots/GIF added
- No secrets committed
