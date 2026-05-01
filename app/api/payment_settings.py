from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.permissions import AuthContext, require_org_admin, require_org_user
from app.core.db import get_db
from app.models.schemas import ConnectStripeStartResponse, OrganizationPaymentSettingsResponse
from app.services.payment_service import service as payment_service

router = APIRouter(prefix="/api/organizations/{org_id}/payment-settings", tags=["payment-settings"])


def _ensure_org_access(org_id: int, auth: AuthContext) -> None:
    if auth.organization_id != org_id:
        raise HTTPException(status_code=403, detail="You can only access payment settings in your own organization")


@router.get("", response_model=OrganizationPaymentSettingsResponse)
def get_payment_settings(
    org_id: int,
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    return payment_service.get_or_create_settings(db, organization_id=org_id)


@router.post("/stripe/connect", response_model=ConnectStripeStartResponse)
def start_stripe_connect(
    org_id: int,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    try:
        url = payment_service.create_connect_link(db, organization_id=org_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ConnectStripeStartResponse(url=url)


@router.post("/stripe/refresh", response_model=OrganizationPaymentSettingsResponse)
def refresh_stripe_connect(
    org_id: int,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    settings = payment_service.get_or_create_settings(db, organization_id=org_id)
    try:
        return payment_service.refresh_connect_status(db, settings=settings)
    except Exception as exc:
        settings.stripe_connect_status = "error"
        settings.stripe_last_error = str(exc)[:1000]
        settings.payments_enabled = False
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings
