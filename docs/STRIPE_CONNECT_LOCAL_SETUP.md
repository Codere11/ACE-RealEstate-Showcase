# Stripe Connect Local Setup

This document describes the recommended local setup for Stripe Connect in ACE Reception Services.

## Goal
Platform-level Stripe configuration should happen once.
After that, a business owner or demo user should be able to:
- open the Java dashboard
- click **Connect Stripe**
- complete Stripe onboarding
- send payment requests from the lead thread flow

## Recommended local setup
Use:
- Java app on `http://127.0.0.1:8080`
- Python runtime service on `http://127.0.0.1:8000` when needed
- public HTTPS tunnel for Stripe callbacks
- Stripe CLI for webhook forwarding

## 1. Required env vars
Set these in `.env`:

```env
ACE_PAYMENT_PROVIDER=mock
ACE_PUBLIC_BASE_URL=https://YOUR_PUBLIC_BASE_URL
STRIPE_SECRET_KEY=sk_test_...
STRIPE_CONNECT_CLIENT_ID=ca_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Notes:
- `ACE_PUBLIC_BASE_URL` must be public HTTPS, not localhost
- `STRIPE_SECRET_KEY` is the platform test secret
- `STRIPE_CONNECT_CLIENT_ID` is the test Connect client id
- `STRIPE_WEBHOOK_SECRET` usually comes from Stripe CLI during local testing

## 2. Start local app
### Infrastructure
```bash
docker compose -f docker-compose-simple.yml up -d
```

### Java app
```bash
cd java-platform
./mvnw spring-boot:run
```

### Optional Python runtime
```bash
./run_backend.sh
```

## 3. Public tunnel
Example with ngrok:

```bash
ngrok http 8080
```

Use the generated HTTPS URL as `ACE_PUBLIC_BASE_URL`.

## 4. Stripe Connect redirect URI
Whitelist this exact redirect URI in Stripe test settings:

```text
https://YOUR_PUBLIC_BASE_URL/api/public/payments/stripe/connect/callback
```

That URI must match the public base URL used by the Java app.

## 5. Webhooks
Use Stripe CLI locally:

```bash
stripe listen --forward-to localhost:8080/api/payments/webhooks/stripe
```

Forward at least:
- `account.updated`
- `checkout.session.completed`

## 6. Local manager flow
1. open `http://127.0.0.1:8080/login`
2. sign in with demo credentials
3. open the organization dashboard
4. go to the **Payments** tab
5. click **Connect Stripe**
6. complete Stripe onboarding
7. refresh status if needed
8. open a lead and send a payment request

## 7. Local fallback behavior
If the connected account is not fully payment-ready yet, ACE Reception Services can still open a Stripe-hosted demo checkout path so the flow remains testable.

## 8. Relevant routes
### Java dashboard routes
- `GET /api/organizations/{org_id}/payment-settings`
- `POST /api/organizations/{org_id}/payment-settings/stripe/connect`
- `POST /api/organizations/{org_id}/payment-settings/stripe/refresh`
- `POST /api/organizations/{org_id}/payment-requests`
- `GET /api/organizations/{org_id}/payment-requests?sid=...`

### Public/payment routes
- `GET /api/public/payments/stripe/connect/callback`
- `POST /api/payments/webhooks/stripe`
- `GET /pay/{public_token}`
- `GET /pay/success`
- `GET /pay/cancel`
