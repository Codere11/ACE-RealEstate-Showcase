# Live Deployment Blueprint

This is the recommended production/demo deployment shape for ACE e-Counter.

## Recommended platform choice
### Railway + LiveKit Cloud
Best current option because it gives:
- fast public launch
- low ops work
- clean multi-service setup
- managed PostgreSQL
- easy env var management
- easy custom domain setup

## Service layout
### Public service
- **Java app** (`java-platform/`)
- public domain
- serves public visitor routes, login, dashboard, Stripe callback, and Stripe webhook

### Private service
- **Python runtime** (`app/`)
- internal/private Railway service
- not exposed publicly unless absolutely necessary
- Java app calls it over internal networking

### Database
- managed PostgreSQL

### Media
- **LiveKit Cloud**

## Domains and subdomains
### Minimum required
Use one public subdomain for the Java app:
- `demo.yourdomain.com`

That single domain can serve:
- public visitor routes
- manager login
- dashboard
- Stripe callback route
- Stripe webhook route

### Optional
- `live.yourdomain.com` if you later want a custom-branded LiveKit endpoint
- no public subdomain needed for Python runtime if it stays private

## Environment variables
### Java app
Required:
- `SPRING_PROFILES_ACTIVE=demo` for public demo with seeded org/user
- `ACE_DB_URL`
- `ACE_DB_USERNAME`
- `ACE_DB_PASSWORD`
- `ACE_SECRET`
- `ACE_PUBLIC_BASE_URL=https://demo.yourdomain.com`
- `ace.python-backend-url=http://<internal-runtime-service>`
- `OPENAI_API_KEY`
- `ACE_LLM_PROVIDER`
- `ACE_LLM_MODEL`
- `STRIPE_SECRET_KEY`
- `STRIPE_CONNECT_CLIENT_ID`
- `STRIPE_WEBHOOK_SECRET`
- `ACE_LIVEKIT_WS_URL=wss://<your-livekit-cloud-host>`
- `ACE_LIVEKIT_API_KEY`
- `ACE_LIVEKIT_API_SECRET`

Optional demo-seed overrides:
- `ace.demo.org-name`
- `ace.demo.org-slug`
- `ace.demo.admin-username`
- `ace.demo.admin-email`
- `ace.demo.admin-password`

### Python runtime
Required:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `ACE_LLM_PROVIDER`
- `ACE_LLM_MODEL`
- `ACE_SECRET`
- `ACE_PUBLIC_BASE_URL=https://demo.yourdomain.com`
- `ACE_LIVEKIT_WS_URL=wss://<your-livekit-cloud-host>`
- `ACE_LIVEKIT_API_KEY`
- `ACE_LIVEKIT_API_SECRET`

## Stripe setup
Use the Java public domain for Stripe.

### Callback whitelist
- `https://demo.yourdomain.com/api/public/payments/stripe/connect/callback`

### Webhook target
- `https://demo.yourdomain.com/api/payments/webhooks/stripe`

## LiveKit setup
Recommended:
- create LiveKit Cloud project
- use its public WSS URL
- place that URL in `ACE_LIVEKIT_WS_URL`
- use project API key/secret for token generation

## Build configuration
### Java app
Use:
- `java-platform/Dockerfile`

### Python runtime
Current repo already has a Python Dockerfile at repo root.
That can be used for the runtime service.

## Readiness notes
### Good to go
- Java app works locally
- Python runtime works locally
- payment flow exists
- live-help flow exists
- public routes exist

### Must still be done outside repo
- Railway project/service creation
- domain DNS records
- LiveKit Cloud project creation
- Stripe production/test dashboard setup
- final env injection

## Recommended rollout order
1. deploy PostgreSQL
2. deploy Python runtime privately
3. deploy Java app publicly
4. attach `demo.yourdomain.com`
5. verify login + dashboard + public route
6. wire Stripe callback/webhook
7. wire LiveKit Cloud
8. run full smoke test
