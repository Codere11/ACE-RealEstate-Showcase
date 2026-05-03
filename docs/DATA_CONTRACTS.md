# Data Contracts

## Purpose
Defines the canonical data shapes for the new AI qualifier and video takeover systems.

These contracts should guide:
- SQLAlchemy models in `app/models/orm.py`
- Pydantic schemas in `app/models/schemas.py`
- frontend TypeScript models/services
- event payloads

---

## 1. QualifierConfig
Represents one editable qualifier configuration.

```json
{
  "id": 1,
  "organization_id": 12,
  "name": "Default AI Qualifier",
  "slug": "default-ai-qualifier",
  "status": "draft",
  "system_prompt": "...",
  "assistant_style": "friendly, concise, consultative",
  "goal_definition": "understand visitor needs, qualify intent, decide escalation",
  "field_schema": {
    "intent": {"type": "string", "required": false},
    "urgency": {"type": "string", "required": false},
    "timeline": {"type": "string", "required": false},
    "budget": {"type": "string", "required": false},
    "location": {"type": "string", "required": false},
    "contact_name": {"type": "string", "required": false},
    "contact_email": {"type": "string", "required": false},
    "contact_phone": {"type": "string", "required": false},
    "objections": {"type": "array", "required": false}
  },
  "required_fields": ["intent"],
  "scoring_rules": {
    "weights": {},
    "notes": "Model may score, backend may post-process"
  },
  "band_thresholds": {
    "hot_min": 80,
    "warm_min": 50,
    "cold_max": 49
  },
  "confidence_thresholds": {
    "overall_min_for_takeover": 0.7,
    "field_min_for_fact_persistence": 0.6
  },
  "takeover_rules": {
    "offer_on_explicit_human_request": true,
    "offer_on_hot_band": true,
    "offer_on_video_eligible": true
  },
  "video_offer_rules": {
    "enabled": true,
    "requires_takeover_eligible": true,
    "operator_can_offer_manually": true
  },
  "rag_enabled": false,
  "knowledge_source_ids": [],
  "max_clarifying_questions": 3,
  "contact_capture_policy": "when_high_intent_or_explicit",
  "version": 1,
  "version_notes": "Initial config",
  "created_at": "2026-04-29T22:00:00Z",
  "updated_at": "2026-04-29T22:00:00Z",
  "published_at": null
}
```

### Notes
- `status`: `draft | live | archived`
- only one live qualifier per org for MVP
- `field_schema` should be flexible JSON, not hardcoded columns only

---

## 2. LeadProfile
Canonical structured qualification result for one session (`sid`).

```json
{
  "id": 55,
  "organization_id": 12,
  "sid": "SID_abc123",
  "qualifier_id": 1,
  "qualifier_version": 3,
  "profile": {
    "intent": "needs help",
    "urgency": "high",
    "timeline": "this_week",
    "budget": "unknown",
    "location": "Ljubljana",
    "contact_name": "Maks",
    "contact_email": "",
    "contact_phone": "",
    "objections": ["price_uncertainty"]
  },
  "field_confidence": {
    "intent": 0.92,
    "urgency": 0.81,
    "timeline": 0.73,
    "budget": 0.22,
    "location": 0.84
  },
  "qualification_score": 86,
  "qualification_band": "hot",
  "confidence_overall": 0.82,
  "reasoning": "High intent and short timeline detected from recent messages.",
  "recommended_next_action": "offer_human_takeover",
  "missing_fields": ["contact_phone", "budget"],
  "takeover_eligible": true,
  "video_offer_eligible": true,
  "last_qualified_at": "2026-04-29T22:05:00Z",
  "created_at": "2026-04-29T22:01:00Z",
  "updated_at": "2026-04-29T22:05:00Z"
}
```

### Notes
- `profile` should be flexible JSON
- `field_confidence` should be JSON keyed by field name
- `reasoning` should be short and operator-focused
- `recommended_next_action` should be machine-friendly

---

## 3. QualifierRun
Audit/debug record of one execution.

```json
{
  "id": 301,
  "organization_id": 12,
  "sid": "SID_abc123",
  "qualifier_id": 1,
  "qualifier_version": 3,
  "trigger": "user_message",
  "input_message_ids": [1001, 1002, 1003],
  "input_excerpt": "...",
  "output_profile_patch": {
    "timeline": "this_week",
    "urgency": "high"
  },
  "score_before": 72,
  "score_after": 86,
  "band_before": "warm",
  "band_after": "hot",
  "confidence_overall": 0.82,
  "reasoning": "...",
  "takeover_eligible": true,
  "video_offer_eligible": true,
  "model_name": "gpt-4.1-mini",
  "latency_ms": 820,
  "created_at": "2026-04-29T22:05:00Z"
}
```

---

## 4. Chat API Response Extension
Current chat responses should be extendable with qualifier-aware metadata.

Suggested response additions:

```json
{
  "reply": "...",
  "chatMode": "open",
  "ui": {"openInput": true},
  "qualifier": {
    "band": "hot",
    "confidence": 0.82,
    "takeoverEligible": true,
    "videoOfferEligible": true,
    "suggestedNextQuestion": "..."
  },
  "takeover": {
    "eligible": true,
    "videoEligible": true,
    "offerState": "available"
  }
}
```

### Notes
- keep these optional for backward compatibility
- dashboard can also rely on live events + fetch endpoints

---

## 5. LiveSession
Canonical one-way live-help session for one visitor session (`sid`).

```json
{
  "id": 12,
  "organization_id": 1,
  "sid": "SID_abc123",
  "manager_user_id": 9,
  "manager_display_name": "Alex",
  "provider": "livekit",
  "status": "live",
  "room_name": "org-1-live-SID_abc123",
  "stage_message": "Alex is joining to help.",
  "ws_url": "ws://127.0.0.1:7880",
  "token": "<ephemeral-token>",
  "started_at": "2026-05-03T09:00:00Z",
  "live_at": "2026-05-03T09:00:05Z",
  "ended_at": null,
  "created_at": "2026-05-03T09:00:00Z",
  "updated_at": "2026-05-03T09:00:05Z"
}
```

### Notes
- current implementation is **one-way**: manager publishes, visitor subscribes
- manager-side rectangle is used for preview/live state
- visitor-side top rectangle is used for joining/live state
- tokens should be short-lived and issued by the backend
- current local development transport is LiveKit

---

## 6. OrganizationPaymentSettings
Canonical per-organization payment/Stripe Connect state.

```json
{
  "id": 3,
  "organization_id": 12,
  "provider": "stripe",
  "mode": "stripe_connect_standard",
  "payments_enabled": true,
  "default_currency": "EUR",
  "stripe_account_id": "acct_123",
  "stripe_connect_status": "connected",
  "stripe_onboarding_complete": true,
  "stripe_details_submitted": true,
  "stripe_charges_enabled": true,
  "stripe_payouts_enabled": true,
  "stripe_publishable_key": "pk_test_...",
  "stripe_scope": "read_write",
  "stripe_livemode": false,
  "stripe_last_error": null,
  "last_synced_at": "2026-05-01T10:00:00Z",
  "created_at": "2026-05-01T09:40:00Z",
  "updated_at": "2026-05-01T10:00:00Z"
}
```

### Notes
- one payment settings record per organization
- this is platform-managed config/state, not lead-specific data
- tenant/business-owner UX should not require manual key pasting

---

## 7. PaymentRequest
Canonical manager-issued payment request for one session (`sid`).

```json
{
  "id": 91,
  "organization_id": 12,
  "sid": "SID_abc123",
  "created_by_user_id": 9,
  "provider": "stripe_connect",
  "provider_payment_id": "pi_123",
  "provider_session_id": "cs_test_123",
  "public_token": "abc123token",
  "amount_cents": 15000,
  "currency": "EUR",
  "purpose": "Reservation deposit",
  "note": "Reserve the property viewing slot.",
  "status": "sent",
  "payment_url": "https://checkout.stripe.com/...",
  "expires_at": "2026-05-02T10:00:00Z",
  "paid_at": null,
  "provider_payload": {
    "mode": "stripe_connect_checkout",
    "stripe_account_id": "acct_123"
  },
  "created_at": "2026-05-01T10:00:00Z",
  "updated_at": "2026-05-01T10:00:00Z"
}
```

### Notes
- `status`: `draft | sent | paid | failed | expired | cancelled`
- provider may currently be one of:
  - `stripe_connect` for connected-account checkout
  - `stripe_demo` for platform-hosted demo checkout
  - `mock` if Stripe is not configured at all
- payment request belongs to an organization and a chat session (`sid`)
- the visitor should receive a hosted pay-now experience, not raw card fields inside the chatbot UI

---

## 7. VideoSession
Canonical room/session state for video escalation.

```json
{
  "id": 77,
  "organization_id": 12,
  "sid": "SID_abc123",
  "provider": "livekit",
  "room_id": "room_123",
  "room_name": "ace-sid-abc123",
  "room_url": "https://...",
  "rep_user_id": 9,
  "status": "ready",
  "offer_origin": "qualifier",
  "offered_at": "2026-04-29T22:06:00Z",
  "accepted_at": "2026-04-29T22:06:20Z",
  "joined_at": null,
  "ended_at": null,
  "recording_enabled": false,
  "recording_status": "not_started",
  "created_at": "2026-04-29T22:06:00Z",
  "updated_at": "2026-04-29T22:06:20Z"
}
```

### Allowed statuses
- `offered`
- `accepted`
- `ready`
- `live`
- `ended`
- `failed`
- `declined`

---

## 8. Frontend TypeScript Models To Add
Manager dashboard:
- `Qualifier`
- `LeadProfile`
- `QualifierRun`
- `OrganizationPaymentSettings`
- `PaymentRequest`
- `VideoSession`

Files to create/update:
- `frontend/manager-dashboard/src/app/models/qualifier.model.ts`
- `frontend/manager-dashboard/src/app/models/lead-profile.model.ts`
- `frontend/manager-dashboard/src/app/models/video-session.model.ts`
- `frontend/manager-dashboard/src/app/services/dashboard.service.ts`

---

## 9. Backend Files To Add/Modify
### Add
- `app/api/qualifiers.py`
- `app/api/payment_settings.py`
- `app/api/payments.py`
- `app/api/public_payment_settings.py`
- `app/api/public_payments.py`
- `app/api/stripe_webhooks.py`
- `app/api/video.py`
- `app/services/llm_service.py`
- `app/services/payment_service.py`
- `app/services/qualifier_service.py`
- `app/services/video_service.py`

### Modify
- `app/models/orm.py`
- `app/models/schemas.py`
- `app/api/chat.py`
- `app/main.py`

---

## 10. Contract Rules
1. Unknown values are allowed and must not be treated as confirmed facts.
2. Confidence is required for extracted fields.
3. Qualification score is always backend-persisted as integer 0-100.
4. Band is always one of `hot | warm | cold`.
5. Takeover/video eligibility are explicit booleans, not inferred from UI only.
6. Every lead profile must reference the qualifier version used.
7. Video session is a separate object linked by `sid`.
8. Payment settings are organization-scoped, not lead-scoped.
9. Tenant/business-owner setup should not require `.env`; only platform/deployment setup should.
