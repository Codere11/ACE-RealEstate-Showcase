from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from sqlalchemy.orm import Session

from app.core.env import load_local_env
from app.models.orm import OrganizationPaymentSettings, PaymentRequest

load_local_env()


@dataclass
class CreatedPaymentLink:
    provider: str
    payment_url: str
    provider_payment_id: Optional[str] = None
    provider_session_id: Optional[str] = None
    provider_payload: Optional[dict] = None


class PaymentService:
    def __init__(self) -> None:
        self.fallback_provider = (os.getenv("ACE_PAYMENT_PROVIDER") or "mock").strip().lower()
        self.public_base_url = (os.getenv("ACE_PUBLIC_BASE_URL") or "http://localhost:8000").rstrip("/")
        self.dashboard_base_url = (os.getenv("ACE_MANAGER_DASHBOARD_URL") or "http://localhost:4400").rstrip("/")
        self.stripe_secret_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
        self.stripe_connect_client_id = (os.getenv("STRIPE_CONNECT_CLIENT_ID") or "").strip()

    # --------------------------- payment settings ---------------------------
    def get_or_create_settings(self, db: Session, *, organization_id: int) -> OrganizationPaymentSettings:
        settings = db.query(OrganizationPaymentSettings).filter(
            OrganizationPaymentSettings.organization_id == organization_id
        ).first()
        if settings:
            return settings
        settings = OrganizationPaymentSettings(
            organization_id=organization_id,
            provider="stripe",
            mode="stripe_connect_standard",
            payments_enabled=False,
            default_currency="EUR",
            stripe_connect_status="not_connected",
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    def refresh_connect_status(self, db: Session, *, settings: OrganizationPaymentSettings) -> OrganizationPaymentSettings:
        if not settings.stripe_account_id or not self.stripe_secret_key:
            settings.payments_enabled = False
            settings.stripe_connect_status = "not_connected"
            settings.last_synced_at = datetime.utcnow()
            db.add(settings)
            db.commit()
            db.refresh(settings)
            return settings

        response = requests.get(
            f"https://api.stripe.com/v1/accounts/{settings.stripe_account_id}",
            auth=(self.stripe_secret_key, ""),
            timeout=20,
        )
        response.raise_for_status()
        account = response.json()
        settings.stripe_onboarding_complete = bool(account.get("details_submitted"))
        settings.stripe_details_submitted = bool(account.get("details_submitted"))
        settings.stripe_charges_enabled = bool(account.get("charges_enabled"))
        settings.stripe_payouts_enabled = bool(account.get("payouts_enabled"))
        settings.stripe_livemode = bool(account.get("livemode"))
        settings.stripe_last_error = None
        settings.last_synced_at = datetime.utcnow()
        settings.payments_enabled = bool(settings.stripe_charges_enabled)
        settings.stripe_connect_status = "connected" if settings.payments_enabled else "restricted"
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    def create_connect_link(self, db: Session, *, organization_id: int) -> str:
        if not self.stripe_connect_client_id:
            raise RuntimeError("Missing STRIPE_CONNECT_CLIENT_ID")

        settings = self.get_or_create_settings(db, organization_id=organization_id)
        state = secrets.token_urlsafe(24)
        settings.stripe_oauth_state = state
        settings.stripe_connect_status = "pending"
        settings.stripe_last_error = None
        db.add(settings)
        db.commit()

        params = {
            "response_type": "code",
            "client_id": self.stripe_connect_client_id,
            "scope": "read_write",
            "state": state,
            "redirect_uri": f"{self.public_base_url}/api/public/payments/stripe/connect/callback",
            "suggested_capabilities[]": "transfers",
            "stripe_user[business_type]": "company",
        }
        return f"https://connect.stripe.com/oauth/authorize?{urlencode(params, doseq=True)}"

    def handle_connect_callback(self, db: Session, *, state: str, code: str) -> OrganizationPaymentSettings:
        settings = db.query(OrganizationPaymentSettings).filter(
            OrganizationPaymentSettings.stripe_oauth_state == state
        ).first()
        if not settings:
            raise ValueError("Invalid or expired Stripe connect state")
        if not self.stripe_secret_key:
            raise RuntimeError("Missing STRIPE_SECRET_KEY")

        response = requests.post(
            "https://connect.stripe.com/oauth/token",
            auth=(self.stripe_secret_key, ""),
            data={
                "grant_type": "authorization_code",
                "code": code,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        settings.stripe_account_id = data.get("stripe_user_id")
        settings.stripe_access_token = data.get("access_token")
        settings.stripe_refresh_token = data.get("refresh_token")
        settings.stripe_publishable_key = data.get("stripe_publishable_key")
        settings.stripe_scope = data.get("scope")
        settings.stripe_livemode = bool(data.get("livemode"))
        settings.stripe_oauth_state = None
        settings.stripe_last_error = None
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return self.refresh_connect_status(db, settings=settings)

    def mark_connect_error(self, db: Session, *, state: Optional[str], error_message: str) -> Optional[OrganizationPaymentSettings]:
        if not state:
            return None
        settings = db.query(OrganizationPaymentSettings).filter(
            OrganizationPaymentSettings.stripe_oauth_state == state
        ).first()
        if not settings:
            return None
        settings.stripe_connect_status = "error"
        settings.stripe_last_error = error_message[:1000]
        settings.stripe_oauth_state = None
        settings.payments_enabled = False
        settings.last_synced_at = datetime.utcnow()
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    # --------------------------- payment requests ---------------------------
    def create_payment_request(
        self,
        db: Session,
        *,
        organization_id: int,
        sid: str,
        created_by_user_id: Optional[int],
        amount: float,
        currency: str,
        purpose: str,
        note: str = "",
        expires_in_hours: Optional[int] = 24,
    ) -> PaymentRequest:
        amount_cents = max(int(round(float(amount) * 100)), 1)
        settings = self.get_or_create_settings(db, organization_id=organization_id)
        provider = self._resolve_provider(settings)
        currency_norm = (currency or settings.default_currency or "EUR").strip().upper()

        payment_request = PaymentRequest(
            organization_id=organization_id,
            sid=sid,
            created_by_user_id=created_by_user_id,
            provider=provider,
            public_token=secrets.token_urlsafe(18),
            amount_cents=amount_cents,
            currency=currency_norm,
            purpose=(purpose or "Payment request").strip(),
            note=(note or "").strip(),
            status="draft",
            payment_url="",
            expires_at=(datetime.utcnow() + timedelta(hours=expires_in_hours)) if expires_in_hours else None,
        )
        db.add(payment_request)
        db.flush()

        link = self._build_link(payment_request, settings=settings)
        payment_request.provider = link.provider
        payment_request.payment_url = link.payment_url
        payment_request.provider_payment_id = link.provider_payment_id
        payment_request.provider_session_id = link.provider_session_id
        payment_request.provider_payload = link.provider_payload
        payment_request.status = "sent"

        db.add(payment_request)
        db.commit()
        db.refresh(payment_request)
        return payment_request

    def list_requests(self, db: Session, *, organization_id: int, sid: Optional[str] = None, limit: int = 100) -> list[PaymentRequest]:
        query = db.query(PaymentRequest).filter(PaymentRequest.organization_id == organization_id)
        if sid:
            query = query.filter(PaymentRequest.sid == sid)
        return query.order_by(PaymentRequest.created_at.desc()).limit(limit).all()

    def get_by_id(self, db: Session, *, organization_id: int, request_id: int) -> Optional[PaymentRequest]:
        return db.query(PaymentRequest).filter(
            PaymentRequest.organization_id == organization_id,
            PaymentRequest.id == request_id,
        ).first()

    def get_by_token(self, db: Session, *, public_token: str) -> Optional[PaymentRequest]:
        return db.query(PaymentRequest).filter(PaymentRequest.public_token == public_token).first()

    def mark_paid(
        self,
        db: Session,
        *,
        payment_request: PaymentRequest,
        provider_payment_id: Optional[str] = None,
        provider_session_id: Optional[str] = None,
        provider_payload: Optional[dict] = None,
    ) -> PaymentRequest:
        if payment_request.status == "paid":
            return payment_request
        payment_request.status = "paid"
        payment_request.paid_at = datetime.utcnow()
        if provider_payment_id:
            payment_request.provider_payment_id = provider_payment_id
        if provider_session_id:
            payment_request.provider_session_id = provider_session_id
        if provider_payload:
            payment_request.provider_payload = provider_payload
        db.add(payment_request)
        db.commit()
        db.refresh(payment_request)
        return payment_request

    def mark_cancelled(self, db: Session, *, payment_request: PaymentRequest) -> PaymentRequest:
        if payment_request.status == "paid":
            return payment_request
        payment_request.status = "cancelled"
        db.add(payment_request)
        db.commit()
        db.refresh(payment_request)
        return payment_request

    def verify_stripe_checkout(self, *, session_id: str, stripe_account_id: Optional[str] = None) -> Optional[dict]:
        if not self.stripe_secret_key:
            return None
        headers = {}
        if stripe_account_id:
            headers["Stripe-Account"] = stripe_account_id
        response = requests.get(
            f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
            auth=(self.stripe_secret_key, ""),
            headers=headers,
            timeout=20,
        )
        if response.status_code >= 400:
            return None
        return response.json()

    # ------------------------------ internals ------------------------------
    def _resolve_provider(self, settings: OrganizationPaymentSettings) -> str:
        if settings.stripe_account_id and settings.payments_enabled and self.stripe_secret_key:
            return "stripe_connect"
        if self.stripe_secret_key:
            return "stripe_demo"
        return self.fallback_provider if self.fallback_provider in {"mock"} else "mock"

    def _build_link(self, payment_request: PaymentRequest, *, settings: OrganizationPaymentSettings) -> CreatedPaymentLink:
        if payment_request.provider == "stripe_connect" and self.stripe_secret_key and settings.stripe_account_id:
            try:
                return self._create_stripe_checkout(payment_request, settings=settings)
            except Exception as exc:
                settings.stripe_last_error = str(exc)[:1000]
                settings.stripe_connect_status = "error"
                settings.payments_enabled = False
                settings.last_synced_at = datetime.utcnow()
                raise
        if payment_request.provider == "stripe_demo" and self.stripe_secret_key:
            return self._create_platform_stripe_checkout(payment_request)
        return self._create_mock_link(payment_request)

    def _create_mock_link(self, payment_request: PaymentRequest) -> CreatedPaymentLink:
        return CreatedPaymentLink(
            provider="mock",
            payment_url=f"{self.public_base_url}/pay/{payment_request.public_token}",
            provider_payload={"mode": "mock"},
        )

    def _stripe_checkout_payload(self, payment_request: PaymentRequest) -> dict:
        success_url = (
            f"{self.public_base_url}/pay/success"
            f"?payment_request_id={payment_request.id}&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{self.public_base_url}/pay/cancel?payment_request_id={payment_request.id}"
        payload = {
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(payment_request.id),
            "metadata[payment_request_id]": str(payment_request.id),
            "metadata[sid]": payment_request.sid,
            "metadata[organization_id]": str(payment_request.organization_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": payment_request.currency.lower(),
            "line_items[0][price_data][unit_amount]": str(payment_request.amount_cents),
            "line_items[0][price_data][product_data][name]": payment_request.purpose,
        }
        if payment_request.note:
            payload["line_items[0][price_data][product_data][description]"] = payment_request.note[:500]
        return payload

    def _create_platform_stripe_checkout(self, payment_request: PaymentRequest) -> CreatedPaymentLink:
        response = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(self.stripe_secret_key, ""),
            data=self._stripe_checkout_payload(payment_request),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return CreatedPaymentLink(
            provider="stripe_demo",
            payment_url=data["url"],
            provider_payment_id=data.get("payment_intent"),
            provider_session_id=data.get("id"),
            provider_payload={
                "mode": "stripe_demo_checkout",
                "session_id": data.get("id"),
                "livemode": data.get("livemode", False),
            },
        )

    def _create_stripe_checkout(self, payment_request: PaymentRequest, *, settings: OrganizationPaymentSettings) -> CreatedPaymentLink:
        response = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(self.stripe_secret_key, ""),
            headers={"Stripe-Account": settings.stripe_account_id},
            data=self._stripe_checkout_payload(payment_request),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return CreatedPaymentLink(
            provider="stripe_connect",
            payment_url=data["url"],
            provider_payment_id=data.get("payment_intent"),
            provider_session_id=data.get("id"),
            provider_payload={
                "mode": "stripe_connect_checkout",
                "session_id": data.get("id"),
                "livemode": data.get("livemode", False),
                "stripe_account_id": settings.stripe_account_id,
            },
        )


service = PaymentService()
