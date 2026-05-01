# Stripe Connect Local Setup

This document describes the intended local-development setup for **Stripe Connect Standard** in ACE Real Estate.

## Goal
The goal is:
- platform owner configures Stripe **once**
- business owner later clicks **Connect Stripe** in the dashboard
- business owner does **not** touch `.env`, API keys, or webhook secrets

So the `.env` work below is **platform setup**, not tenant/client setup.

---

## Recommended local architecture
For local testing, expose **only the backend** publicly.

Recommended setup:
- backend runs in Docker on `http://localhost:8000`
- dashboard stays local on `http://localhost:4400`
- chatbot stays local on `http://localhost:4200`
- public backend URL is provided by a tunnel such as **ngrok**
- Stripe webhooks are forwarded with **Stripe CLI**

Why this is the best local workflow:
- Stripe Connect callback needs a public HTTPS URL
- Stripe webhooks are easier to debug/replay with Stripe CLI
- dashboard/chatbot can stay local during development

---

## 1) Required platform env vars
Add these to `.env` before starting/restarting the backend:

```env
ACE_PAYMENT_PROVIDER=mock
ACE_PUBLIC_BASE_URL=https://YOUR_PUBLIC_BACKEND_URL
ACE_MANAGER_DASHBOARD_URL=http://localhost:4400
STRIPE_SECRET_KEY=sk_test_...
STRIPE_CONNECT_CLIENT_ID=ca_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Notes
- `ACE_PUBLIC_BASE_URL` must be the **public backend URL**, not `localhost`
- `ACE_MANAGER_DASHBOARD_URL` can stay local during development
- `STRIPE_SECRET_KEY` is the platform test secret key
- `STRIPE_CONNECT_CLIENT_ID` is the Stripe Connect test client id
- `STRIPE_WEBHOOK_SECRET` comes from Stripe CLI or from a Stripe dashboard webhook endpoint

---

## 2) Docker hookup
The backend container already reads the Stripe env vars from `docker-compose-simple.yml`.

So the normal flow is:

```bash
cp .env.example .env
# edit .env with Stripe/test values
docker compose -f docker-compose-simple.yml up -d --build backend dashboard chatbot
```

If you only changed `.env`, rebuilding backend/dashboard is the safest path during local testing:

```bash
docker compose -f docker-compose-simple.yml up -d --build backend dashboard
```

### Important
The business owner should **never** do this.
This is platform/developer setup only.

---

## 3) Public backend URL with ngrok
Example:

```bash
ngrok http 8000
```

Use the generated HTTPS URL as:

```env
ACE_PUBLIC_BASE_URL=https://abc123.ngrok-free.app
```

Then restart backend.

---

## 4) Stripe Connect redirect URI
In the Stripe Connect/test platform settings, whitelist this exact redirect URI:

```text
https://YOUR_PUBLIC_BACKEND_URL/api/public/payments/stripe/connect/callback
```

Example:

```text
https://abc123.ngrok-free.app/api/public/payments/stripe/connect/callback
```

This must match `ACE_PUBLIC_BASE_URL`.

---

## 5) Stripe webhooks
### Recommended local webhook workflow
Use Stripe CLI locally:

```bash
stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe
```

Stripe CLI will print a webhook signing secret.
Set it as:

```env
STRIPE_WEBHOOK_SECRET=whsec_...
```

Then restart backend.

### Minimal events to support
At minimum, subscribe/forward these event types:
- `account.updated`
- `checkout.session.completed`

---

## 6) Manager/business-owner local UX
Once the platform env/config is in place, the intended manager flow is:

1. open dashboard at `http://localhost:4400/login`
2. go to the **Payments** tab
3. click **Connect Stripe**
4. complete Stripe-hosted onboarding/auth
5. return to dashboard
6. click **Refresh status** if needed
7. once connected, open a lead and click **Send payment link**

That is the intended zero-tech tenant flow.

---

## 7) Testing strategy
For a proper local test, use:
- **one Stripe test platform account** for ACE
- **a different Stripe test account** as the connected seller/business

This mirrors the real Connect architecture better than trying to connect the platform account to itself.

---

## 8) Current local fallback
If the connected Stripe account is not fully payment-ready yet, ACE can still open a **Stripe-hosted demo checkout** on the platform test account.

Why this exists:
- the flow remains demoable now
- the UI stays the same
- later the same flow can switch to connected-account checkout when the seller account becomes fully ready

The intended production-shaped path is still:
- org-level Stripe Connect settings
- hosted Stripe onboarding
- connected-account hosted Stripe Checkout
- webhook-driven payment state updates

---

## 9) Current relevant local endpoints
### Org payment settings
- `GET /api/organizations/{org_id}/payment-settings`
- `POST /api/organizations/{org_id}/payment-settings/stripe/connect`
- `POST /api/organizations/{org_id}/payment-settings/stripe/refresh`

### Payment requests
- `POST /api/organizations/{org_id}/payment-requests`
- `GET /api/organizations/{org_id}/payment-requests?sid=...`

### Public Stripe/connect routes
- `GET /api/public/payments/stripe/connect/callback`
- `POST /api/payments/webhooks/stripe`
- `GET /pay/{public_token}`
- `GET /pay/success`
- `GET /pay/cancel`

---

## Summary
### Platform owner does once
- Stripe test platform setup
- `.env` setup
- ngrok/public backend URL
- redirect URI config
- Stripe CLI/webhook secret

### Business owner does later
- click **Connect Stripe**
- authorize in Stripe
- send payment requests from dashboard

That is the intended architecture.
