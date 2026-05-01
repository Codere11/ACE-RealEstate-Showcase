from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.orm import PaymentRequest
from app.services import event_bus
from app.services.payment_service import service as payment_service

router = APIRouter(tags=["public-payments"])


def _money(amount_cents: int, currency: str) -> str:
    return f"{amount_cents / 100:.2f} {currency.upper()}"


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html>
<html lang='sl'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#f3f4f6; margin:0; padding:32px; color:#111827; }}
    .card {{ max-width:640px; margin:0 auto; background:#fff; border-radius:16px; padding:24px; box-shadow:0 10px 30px rgba(0,0,0,.08); }}
    h1 {{ margin-top:0; font-size:28px; }}
    .amount {{ font-size:34px; font-weight:800; margin:10px 0 18px; }}
    .muted {{ color:#6b7280; }}
    .note {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:12px; padding:12px 14px; margin:16px 0; }}
    .btn {{ display:inline-block; background:#2563eb; color:#fff; border:none; border-radius:10px; padding:12px 18px; font-weight:700; text-decoration:none; cursor:pointer; }}
    .btn.alt {{ background:#e5e7eb; color:#111827; }}
    .row {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }}
    .ok {{ color:#166534; }}
    .warn {{ color:#92400e; }}
  </style>
</head>
<body>
  <div class='card'>{body}</div>
</body>
</html>""")


@router.get("/pay/{public_token}")
def public_payment_page(public_token: str, db: Session = Depends(get_db)):
    payment_request = payment_service.get_by_token(db, public_token=public_token)
    if not payment_request:
        raise HTTPException(status_code=404, detail="Payment request not found")

    if payment_request.status == "paid":
        return _page(
            "Plačilo prejeto",
            f"<h1 class='ok'>Plačilo uspešno prejeto</h1><p class='amount'>{_money(payment_request.amount_cents, payment_request.currency)}</p><p>Hvala. Vaše plačilo za <strong>{payment_request.purpose}</strong> je bilo uspešno evidentirano.</p>",
        )

    if payment_request.provider == "stripe" and payment_request.payment_url.startswith("http"):
        return RedirectResponse(payment_request.payment_url, status_code=302)

    note = f"<div class='note'>{payment_request.note}</div>" if payment_request.note else ""
    expired = payment_request.expires_at and payment_request.expires_at < datetime.utcnow()
    if expired:
        return _page(
            "Zahtevek je potekel",
            f"<h1 class='warn'>Ta zahtevek je potekel</h1><p class='amount'>{_money(payment_request.amount_cents, payment_request.currency)}</p><p class='muted'>{payment_request.purpose}</p>",
        )

    return _page(
        "Plačilo",
        (
            f"<h1>Plačilo</h1>"
            f"<p class='muted'>{payment_request.purpose}</p>"
            f"<div class='amount'>{_money(payment_request.amount_cents, payment_request.currency)}</div>"
            f"{note}"
            f"<p class='muted'>To je lokalni demo plačilni zaslon. V produkciji ga lahko nadomesti Stripe Checkout.</p>"
            f"<form method='post' action='/pay/{payment_request.public_token}/complete'>"
            f"<button class='btn' type='submit'>Potrdi plačilo</button>"
            f"</form>"
        ),
    )


@router.post("/pay/{public_token}/complete")
async def complete_public_payment(public_token: str, db: Session = Depends(get_db)):
    payment_request = payment_service.get_by_token(db, public_token=public_token)
    if not payment_request:
        raise HTTPException(status_code=404, detail="Payment request not found")
    payment_request = payment_service.mark_paid(db, payment_request=payment_request)
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
    return RedirectResponse(f"/pay/{public_token}", status_code=303)


@router.get("/pay/success")
async def stripe_success_page(
    payment_request_id: int = Query(..., ge=1),
    session_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    payment_request = db.query(PaymentRequest).filter(PaymentRequest.id == payment_request_id).first()
    if not payment_request:
        raise HTTPException(status_code=404, detail="Payment request not found")

    stripe_account_id = ((payment_request.provider_payload or {}).get("stripe_account_id") if payment_request.provider_payload else None)
    data = payment_service.verify_stripe_checkout(session_id=session_id, stripe_account_id=stripe_account_id)
    if data and data.get("payment_status") == "paid":
        payment_request = payment_service.mark_paid(
            db,
            payment_request=payment_request,
            provider_payment_id=data.get("payment_intent"),
            provider_session_id=data.get("id"),
            provider_payload={"stripe_session": data},
        )
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
        return _page(
            "Plačilo uspešno",
            f"<h1 class='ok'>Plačilo uspešno</h1><p class='amount'>{_money(payment_request.amount_cents, payment_request.currency)}</p><p>Vaše plačilo je bilo potrjeno.</p>",
        )

    return _page(
        "Plačilo v obdelavi",
        "<h1>Plačilo je še v obdelavi</h1><p>Če je bilo plačilo uspešno, se bo status v sistemu posodobil kmalu.</p>",
    )


@router.get("/pay/cancel")
def stripe_cancel_page(payment_request_id: int = Query(..., ge=1)):
    return _page(
        "Plačilo preklicano",
        "<h1 class='warn'>Plačilo ni bilo dokončano</h1><p>Lahko se vrnete v pogovor in poskusite znova.</p>",
    )
