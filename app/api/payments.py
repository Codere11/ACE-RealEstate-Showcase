from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.permissions import AuthContext, require_org_admin, require_org_user
from app.core.db import get_db
from app.models.schemas import PaymentRequestCreate, PaymentRequestResponse
from app.services import event_bus
from app.services.payment_service import service as payment_service

router = APIRouter(prefix="/api/organizations/{org_id}/payment-requests", tags=["payment-requests"])


def _ensure_org_access(org_id: int, auth: AuthContext) -> None:
    if auth.organization_id != org_id:
        raise HTTPException(status_code=403, detail="You can only access payments in your own organization")


def _serialize_payment_request(pr) -> dict:
    return {
        "id": pr.id,
        "provider": pr.provider,
        "status": pr.status,
        "amountCents": pr.amount_cents,
        "currency": pr.currency,
        "purpose": pr.purpose,
        "note": pr.note,
        "paymentUrl": pr.payment_url,
        "expiresAt": pr.expires_at.isoformat() if pr.expires_at else None,
        "paidAt": pr.paid_at.isoformat() if pr.paid_at else None,
    }


async def _publish_payment_sent(pr) -> None:
    request_payload = _serialize_payment_request(pr)
    await event_bus.publish(pr.sid, "payment.request.sent", request_payload)
    await event_bus.publish(pr.sid, "message.created", {
        "role": "assistant",
        "text": f"Prejeli ste zahtevek za plačilo: {pr.purpose}.",
        "timestamp": int(pr.created_at.timestamp()),
        "ui": {
            "type": "payment_request",
            "request": request_payload,
        },
    })


@router.get("", response_model=list[PaymentRequestResponse])
def list_payment_requests(
    org_id: int,
    sid: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    return payment_service.list_requests(db, organization_id=org_id, sid=sid, limit=limit)


@router.post("", response_model=PaymentRequestResponse, status_code=201)
async def create_payment_request(
    org_id: int,
    payload: PaymentRequestCreate,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    payment_request = payment_service.create_payment_request(
        db,
        organization_id=org_id,
        sid=payload.sid,
        created_by_user_id=auth.user_id,
        amount=payload.amount,
        currency=payload.currency,
        purpose=payload.purpose,
        note=payload.note,
        expires_in_hours=payload.expires_in_hours,
    )
    await _publish_payment_sent(payment_request)
    return payment_request


@router.post("/{request_id}/cancel", response_model=PaymentRequestResponse)
def cancel_payment_request(
    org_id: int,
    request_id: int,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    payment_request = payment_service.get_by_id(db, organization_id=org_id, request_id=request_id)
    if not payment_request:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return payment_service.mark_cancelled(db, payment_request=payment_request)
