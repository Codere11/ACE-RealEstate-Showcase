# Local Development Runbook

## Prerequisites
- Python 3.10+
- Node.js 22+
- Docker + Docker Compose v2

## 1. Environment
```bash
cp env/local.shared.env.example .env
# Edit .env with your OpenAI key and other settings
```

Important variables:
- `OPENAI_API_KEY`
- `ACE_LLM_PROVIDER` (default: openai)
- `ACE_LLM_MODEL` (default: gpt-4.1-mini)
- `ACE_SECRET` — JWT signing secret
- `DATABASE_URL` — PostgreSQL connection
- `ACE_LIVEKIT_WS_URL` — LiveKit WebSocket URL
- `ACE_LIVEKIT_API_KEY` / `ACE_LIVEKIT_API_SECRET` — LiveKit credentials

## 2. Start infrastructure
```bash
docker compose -f docker-compose-simple.yml up -d
```

This starts:
- PostgreSQL on `localhost:5433`
- LiveKit on `localhost:7880`

## 3. Run the Python backend
```bash
cd backend
source ../venv/bin/activate
uvicorn main:app --port 8000 --reload
```

On first startup, it auto-seeds:
- Demo organization (slug: `demo`)
- Admin user (`admin` / `test123`)
- AI Receptor qualifier with Slovenian beauty salon prompt

Health check:
```bash
curl -sf http://127.0.0.1:8000/
```

## 4. Angular visitor development (optional)
```bash
cd angular-visitor
npm start
```
Opens on `http://localhost:4200` with API proxy to port 8000.

## 5. Production build
```bash
cd angular-visitor && npm run build
cp -r dist/angular-visitor/browser/* ../backend/static/
```

## 6. Key routes
- Home: `http://127.0.0.1:8000/`
- Demo credentials: `admin / test123`
- Login: `POST /login` (form: username, password)
- Chat: `POST /chat` (JSON: message, sid, tenant_slug)
- Live session: `GET /api/public/organizations/{slug}/live-session?sid=...`
- Go live: `POST /api/organizations/{org_id}/live-sessions/go-live`

## 7. Notes
- The Python `backend/` is the entire application server — no Java needed
- `app/` is an AI library imported directly by `backend/`, not a separate service
- PostgreSQL is shared
- LiveKit handles real-time video handoff
