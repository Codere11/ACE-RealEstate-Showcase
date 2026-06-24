# WARP.md

ACE — AI SDR for B2B. Qualifies visitors, books insta-meetings, formats meeting notes.

## Start

```bash
docker compose -f docker-compose-simple.yml up -d
```

## URLs

| URL | What |
|---|---|
| `http://localhost:8000/demo` | Visitor chat |
| `http://localhost:8000/demo/dashboard` | Staff dashboard |
| `http://localhost:8000/login` | Login |

Credentials: `admin` / `test123`

## Dev

```bash
# Backend with reload
cd backend && source ../venv/bin/activate
uvicorn main:app --port 8000 --reload

# Angular dev server
cd angular-visitor && npm start

# Rebuild frontend
cd angular-visitor && npm run build
cp -r dist/angular-visitor/browser/* ../backend/static/
```
