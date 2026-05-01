from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.orm import OrganizationPaymentSettings, PaymentRequest
from app.services import event_bus
from app.services.payment_service import service as payment_service

router = APIRouter(prefix="/api/payments/webhooks", tags=["stripe-webhooks"])


def _verify_signature(payload: bytes, signature_header: str | None) -> bool:
    secret = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return False
    if not signature_header:
        return False
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
        timestamp = parts.get("t")
        signature = parts.get("v1")
        if not timestamp or not signature:
            return False
        if abs(time.time() - int(timestamp)) > 300:
            return False
        signed_payload = f"{timestamp}.".encode("utf-8") + payload
        expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


async def _publish_paid(payment_request: PaymentRequest) -> None:
    await event_bus.publish(payment_request.sid, "payment.request.paid", {
        "id": payment_request.id,
        "status": payment_request.status,
        "amountCents": payment_request.amount_cents,
        "currency": payment_request.currency,
        "purpose": payment_request.purpose,
        "paidAt": payment_request.paid_at.isoformat() if payment_request.paid_at else None,
    })
    await event_bus.publish(payment_request.sid, "message.created", {
        "role": "assistant",
        "text": f"Plačilo uspešno prejeto za: {payment_request.purpose}.",
        "timestamp": int(payment_request.updated_at.timestamp()),
    })


@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")):
    payload = await request.body()
    if not _verify_signature(payload, stripe_signature):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    evt = json.loads(payload.decode("utf-8"))
    evt_type = evt.get("type")
    data = ((evt.get("data") or {}).get("object") or {})

    db: Session = SessionLocal()
    try:
        if evt_type == "account.updated":
            stripe_account_id = data.get("id")
            if stripe_account_id:
                settings = db.query(OrganizationPaymentSettings).filter(
                    OrganizationPaymentSettings.stripe_account_id == stripe_account_id
                ).first()
                if settings:
                    settings.stripe_onboarding_complete = bool(data.get("details_submitted"))
                    settings.stripe_details_submitted = bool(data.get("details_submitted"))
                    settings.stripe_charges_enabled = bool(data.get("charges_enabled"))
                    settings.stripe_payouts_enabled = bool(data.get("payouts_enabled"))
                    settings.stripe_livemode = bool(data.get("livemode"))
                    settings.payments_enabled = bool(settings.stripe_charges_enabled)
                    settings.stripe_connect_status = "connected" if settings.payments_enabled else "restricted"
                    settings.last_synced_at = datetime.utcnow()
                    db.add(settings)
                    db.commit()
            return {"ok": True}

        if evt_type == "checkout.session.completed":
            metadata = data.get("metadata") or {}
            payment_request_id = metadata.get("payment_request_id") or data.get("client_reference_id")
            if payment_request_id:
                payment_request = db.query(PaymentRequest).filter(PaymentRequest.id == int(payment_request_id)).first()
                if payment_request:
                    payment_request = payment_service.mark_paid(
                        db,
                        payment_request=payment_request,
                        provider_payment_id=data.get("payment_intent"),
                        provider_session_id=data.get("id"),
                        provider_payload={"stripe_session": data},
                    )
                    await _publish_paid(payment_request)
            return {"ok": True}

        return {"ok": True, "ignored": evt_type}
    finally:
        db.close()
