<!-- Created: 2026-04-18T12:20:22Z -->
# Local Development Runbook
This runbook is the fastest path to running ACE Real Estate locally.

If you want the big-picture product explanation first, read:
- `docs/PRODUCT_OVERVIEW.md`

## Prerequisites
- Docker
- Docker Compose (v2+)

## 1) Environment Setup
Create your local environment file:

```bash
cp .env.example .env
```

Minimum fields to review in `.env`:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `ACE_LLM_PROVIDER`
- `ACE_LLM_MODEL`
- `ACE_SECRET`
- `ACE_LOG_LEVEL`
- `ACE_ENFORCE_DUAL_CONTACT`

If you want to test Stripe Connect locally, also review:
- `ACE_PUBLIC_BASE_URL`
- `ACE_MANAGER_DASHBOARD_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_CONNECT_CLIENT_ID`
- `STRIPE_WEBHOOK_SECRET`

## 2) Boot
This is the default boot command after a reboot, fresh terminal session, or first local run:

```bash
docker compose -f docker-compose-simple.yml up -d --build
```

If you already built the images and just want to start the stack again, this is usually enough:

```bash
docker compose -f docker-compose-simple.yml up -d
```

## 3) Service Endpoints
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Chatbot frontend: `http://localhost:4200`
- Manager dashboard: `http://localhost:4400`
- Admin portal: `http://localhost:4500`

Useful demo routes:
- Demo chatbot org route: `http://localhost:4200/demo-agency/nepremicnine`
- Manager login: `http://localhost:4400/login`
- Demo manager credentials: `admin / test123`

## 4) Health Checks
Quick checks:

```bash
curl -sf http://localhost:8000/docs
curl -sf http://localhost:4200
curl -sf http://localhost:4400
curl -sf http://localhost:4500
```

## 5) Stripe Connect Local Notes
For local Stripe Connect testing:
- keep dashboard/chatbot local
- expose **only the backend** publicly (recommended: `ngrok http 8000`)
- point `ACE_PUBLIC_BASE_URL` to that public backend URL
- keep `ACE_MANAGER_DASHBOARD_URL=http://localhost:4400`
- use Stripe CLI for webhooks:

```bash
stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe
```

After changing Stripe-related env vars, rebuild/restart backend:

```bash
docker compose -f docker-compose-simple.yml up -d --build backend dashboard
```

Full walkthrough:
- `docs/STRIPE_CONNECT_LOCAL_SETUP.md`

Important distinction:
- `.env` / ngrok / Stripe CLI setup is **platform/developer setup**
- the intended business-owner UX is still just **Connect Stripe** inside the dashboard

### Boot with Stripe demo enabled
If you want the full local Stripe demo after a reboot, the boot sequence is:

1. start the stack
   ```bash
   docker compose -f docker-compose-simple.yml up -d --build
   ```
2. start a public backend tunnel
   ```bash
   ngrok http 8000
   ```
3. if ngrok gives you a new URL, update `ACE_PUBLIC_BASE_URL` in `.env`
4. start Stripe webhook forwarding
   ```bash
   stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe
   ```
5. if you changed `.env`, restart backend/dashboard
   ```bash
   docker compose -f docker-compose-simple.yml up -d --build backend dashboard
   ```

This keeps the product boot process simple:
- plain local app boot for normal development
- extra tunnel/webhook boot only when you want the Stripe demo flow

## 6) Logs and Troubleshooting
View all logs:

```bash
docker compose -f docker-compose-simple.yml logs -f
```

View backend logs only:

```bash
docker compose -f docker-compose-simple.yml logs -f backend
```

Restart stack:

```bash
docker compose -f docker-compose-simple.yml restart
```

Stop stack:

```bash
docker compose -f docker-compose-simple.yml down
```

## 7) Data Notes
- Local PostgreSQL is mapped in Docker volume `postgres_data`
- Keep secrets out of git
- Use `.env.example` as baseline for sharing config
- The AI qualifier is DB-backed and can be seeded for local demo/testing

Seed the default demo qualifier:

```bash
docker compose -f docker-compose-simple.yml exec backend python scripts/seed_default_qualifier.py
```

The chatbot will switch to open qualifier mode automatically when a live qualifier exists for the organization.

## 8) Alternative Compose Files
- `docker-compose-simple.yml`: easiest full-stack local run
- `docker-compose.yml`: full/default compose
- `docker-compose.dev.yml`: development variant
- `docker-compose.hotreload.yml`: hot-reload focused variant
