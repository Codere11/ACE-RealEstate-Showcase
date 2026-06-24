# WARP.md

ACE — AI SDR that qualifies B2B website visitors and books insta-meetings with your sales team.

## Stack
- `angular-visitor/` — Angular 19 SPA (visitor chat + staff dashboard)
- `backend/` — Python FastAPI (API, auth, AI integration, static serving)
- `app/` — Python AI library (LangGraph graph, B2B tools, LLM client)

## Quick commands

### Start everything (Docker)
```bash
docker compose -f docker-compose-simple.yml up -d
```

### Backend (local dev)
```bash
cd backend && source ../venv/bin/activate
uvicorn main:app --port 8000 --reload
```

### Angular dev server (only if editing frontend)
```bash
cd angular-visitor && npm start
```

### Rebuild frontend
```bash
cd angular-visitor && npm run build
cp -r dist/angular-visitor/browser/* ../backend/static/
```

### Run tests
```bash
cd backend && source ../venv/bin/activate
python -m pytest ../tests/ -v
```

### B2B simulator
```bash
cd scripts && source ../venv/bin/activate
python simulate_b2b.py
```

## Local URLs
- Visitor chat: `http://localhost:8000/demo`
- Staff dashboard: `http://localhost:8000/demo/dashboard`
- Login: `http://localhost:8000/login`
- Admin: `http://localhost:8000/admin/dashboard`

## Credentials
- Username: `admin`
- Password: `test123`
