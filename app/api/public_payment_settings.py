from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.payment_service import service as payment_service

router = APIRouter(tags=["public-payment-settings"])


def _redirect(status: str, message: str = "") -> RedirectResponse:
    base = payment_service.dashboard_base_url
    suffix = f"?tab=payments&stripe={status}"
    if message:
        from urllib.parse import quote
        suffix += f"&message={quote(message)}"
    return RedirectResponse(base + suffix, status_code=302)


@router.get("/api/public/payments/stripe/connect/callback")
def stripe_connect_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if error:
        payment_service.mark_connect_error(db, state=state, error_message=error_description or error)
        return _redirect("error", error_description or error)
    if not code or not state:
        return _redirect("error", "Missing Stripe callback parameters")
    try:
        payment_service.handle_connect_callback(db, state=state, code=code)
        return _redirect("connected")
    except Exception as exc:
        payment_service.mark_connect_error(db, state=state, error_message=str(exc))
        return _redirect("error", str(exc))
