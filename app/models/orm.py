# app/models/orm.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.db import Base

# ---------- Users (Authentication) ----------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    # Role: 'org_admin' (manage org users + surveys) or 'org_user' (view only)
    role: Mapped[str] = mapped_column(String(20), default="org_user")
    
    # Profile picture URL
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Required: link to organization (no system admins in DB)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")

    __table_args__ = (
        CheckConstraint("role IN ('org_admin', 'org_user')", name="chk_users_role"),
        Index("ix_users_role_active", "role", "is_active"),
    )

# ---------- Organizations (formerly Clients) ----------
class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # e.g., "novak-realty"
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # human name
    name: Mapped[str] = mapped_column(String(160), index=True)
    # optional subdomain, e.g., "ace.novak.si"
    subdomain: Mapped[Optional[str]] = mapped_column(String(160))
    # on/off
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    users: Mapped[list[User]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    surveys: Mapped[list["Survey"]] = relationship(
        "Survey", back_populates="organization", cascade="all, delete-orphan"
    )
    survey_responses: Mapped[list["SurveyResponse"]] = relationship(
        "SurveyResponse", back_populates="organization", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="organization", cascade="all, delete-orphan"
    )
    leads: Mapped[list["Lead"]] = relationship(
        "Lead", back_populates="organization", cascade="all, delete-orphan"
    )
    qualifiers: Mapped[list["Qualifier"]] = relationship(
        "Qualifier", back_populates="organization", cascade="all, delete-orphan"
    )
    lead_profiles: Mapped[list["LeadProfile"]] = relationship(
        "LeadProfile", back_populates="organization", cascade="all, delete-orphan"
    )
    qualifier_runs: Mapped[list["QualifierRun"]] = relationship(
        "QualifierRun", back_populates="organization", cascade="all, delete-orphan"
    )
    payment_requests: Mapped[list["PaymentRequest"]] = relationship(
        "PaymentRequest", back_populates="organization", cascade="all, delete-orphan"
    )
    live_sessions: Mapped[list["LiveSession"]] = relationship(
        "LiveSession", back_populates="organization", cascade="all, delete-orphan"
    )
    payment_settings: Mapped[Optional["OrganizationPaymentSettings"]] = relationship(
        "OrganizationPaymentSettings", back_populates="organization", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("ix_organizations_active_slug", "active", "slug"),
    )


# Backward compatibility alias
Client = Organization


# ---------- Surveys ----------
class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # Human-readable name
    name: Mapped[str] = mapped_column(String(160), index=True)
    # URL slug (unique per org)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    # Survey type: 'regular' or 'ab_test'
    survey_type: Mapped[str] = mapped_column(String(20), default="regular")
    # Status: 'draft', 'live', 'archived'
    status: Mapped[str] = mapped_column(String(20), default="draft")
    
    # Survey flow JSON (for regular surveys)
    flow_json: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # A/B test variants (only used when survey_type='ab_test')
    variant_a_flow: Mapped[Optional[dict]] = mapped_column(JSON)
    variant_b_flow: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="surveys")
    responses: Mapped[list["SurveyResponse"]] = relationship(
        "SurveyResponse", back_populates="survey", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        CheckConstraint("survey_type IN ('regular', 'ab_test')", name="chk_surveys_type"),
        CheckConstraint("status IN ('draft', 'live', 'archived')", name="chk_surveys_status"),
        UniqueConstraint("organization_id", "slug", name="uq_surveys_org_slug"),
        Index("ix_surveys_org_status", "organization_id", "status"),
    )


# ---------- AI Qualifiers ----------
class Qualifier(Base):
    __tablename__ = "qualifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")

    system_prompt: Mapped[str] = mapped_column(Text, default="")
    assistant_style: Mapped[str] = mapped_column(String(255), default="friendly, concise, consultative")
    goal_definition: Mapped[str] = mapped_column(Text, default="")
    field_schema: Mapped[Optional[dict]] = mapped_column(JSON)
    required_fields: Mapped[Optional[list]] = mapped_column(JSON)
    scoring_rules: Mapped[Optional[dict]] = mapped_column(JSON)
    band_thresholds: Mapped[Optional[dict]] = mapped_column(JSON)
    confidence_thresholds: Mapped[Optional[dict]] = mapped_column(JSON)
    takeover_rules: Mapped[Optional[dict]] = mapped_column(JSON)
    video_offer_rules: Mapped[Optional[dict]] = mapped_column(JSON)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    knowledge_source_ids: Mapped[Optional[list]] = mapped_column(JSON)
    max_clarifying_questions: Mapped[int] = mapped_column(Integer, default=3)
    contact_capture_policy: Mapped[str] = mapped_column(String(64), default="when_high_intent_or_explicit")
    version: Mapped[int] = mapped_column(Integer, default=1)
    version_notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    organization: Mapped[Organization] = relationship("Organization", back_populates="qualifiers")
    lead_profiles: Mapped[list["LeadProfile"]] = relationship(
        "LeadProfile", back_populates="qualifier"
    )
    runs: Mapped[list["QualifierRun"]] = relationship(
        "QualifierRun", back_populates="qualifier"
    )

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'live', 'archived')", name="chk_qualifiers_status"),
        UniqueConstraint("organization_id", "slug", name="uq_qualifiers_org_slug"),
        Index("ix_qualifiers_org_status", "organization_id", "status"),
    )


class LeadProfile(Base):
    __tablename__ = "lead_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sid: Mapped[str] = mapped_column(String(64), index=True)
    qualifier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("qualifiers.id", ondelete="SET NULL"), index=True
    )
    qualifier_version: Mapped[int] = mapped_column(Integer, default=1)

    profile: Mapped[Optional[dict]] = mapped_column(JSON)
    field_confidence: Mapped[Optional[dict]] = mapped_column(JSON)
    qualification_score: Mapped[int] = mapped_column(Integer, default=0)
    qualification_band: Mapped[str] = mapped_column(String(16), default="cold")
    confidence_overall: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    recommended_next_action: Mapped[str] = mapped_column(String(64), default="")
    missing_fields: Mapped[Optional[list]] = mapped_column(JSON)
    takeover_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    video_offer_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    last_qualified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="lead_profiles")
    qualifier: Mapped[Optional[Qualifier]] = relationship("Qualifier", back_populates="lead_profiles")

    __table_args__ = (
        CheckConstraint("qualification_band IN ('hot', 'warm', 'cold')", name="chk_lead_profiles_band"),
        UniqueConstraint("organization_id", "sid", name="uq_lead_profiles_org_sid"),
        Index("ix_lead_profiles_org_band_score", "organization_id", "qualification_band", "qualification_score"),
    )


class QualifierRun(Base):
    __tablename__ = "qualifier_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sid: Mapped[str] = mapped_column(String(64), index=True)
    qualifier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("qualifiers.id", ondelete="SET NULL"), index=True
    )
    qualifier_version: Mapped[int] = mapped_column(Integer, default=1)
    trigger: Mapped[str] = mapped_column(String(40), default="user_message")
    input_message_ids: Mapped[Optional[list]] = mapped_column(JSON)
    input_excerpt: Mapped[str] = mapped_column(Text, default="")
    output_profile_patch: Mapped[Optional[dict]] = mapped_column(JSON)
    score_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    band_before: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    band_after: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    confidence_overall: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    takeover_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    video_offer_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Organization] = relationship("Organization", back_populates="qualifier_runs")
    qualifier: Mapped[Optional[Qualifier]] = relationship("Qualifier", back_populates="runs")

    __table_args__ = (
        CheckConstraint("band_before IS NULL OR band_before IN ('hot', 'warm', 'cold')", name="chk_qualifier_runs_band_before"),
        CheckConstraint("band_after IS NULL OR band_after IN ('hot', 'warm', 'cold')", name="chk_qualifier_runs_band_after"),
        Index("ix_qualifier_runs_org_sid_created", "organization_id", "sid", "created_at"),
    )


# ---------- Survey Responses (formerly Lead data) ----------
class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    
    # Session tracking
    sid: Mapped[str] = mapped_column(String(64), index=True)
    
    # A/B test variant (null for regular surveys, 'a' or 'b' for A/B tests)
    variant: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    
    # Contact information
    name: Mapped[str] = mapped_column(String(160), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    
    # Survey answers and scoring
    survey_answers: Mapped[Optional[dict]] = mapped_column(JSON)  # {node_id: answer}
    score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    interest: Mapped[str] = mapped_column(String(16), default="Low")  # Low/Medium/High
    
    # Survey lifecycle
    survey_started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    survey_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    survey_progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100 percentage
    
    # Additional metadata
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    survey: Mapped[Survey] = relationship("Survey", back_populates="responses")
    organization: Mapped[Organization] = relationship("Organization", back_populates="survey_responses")
    
    __table_args__ = (
        CheckConstraint("variant IS NULL OR variant IN ('a', 'b')", name="chk_responses_variant"),
        CheckConstraint("interest IN ('Low', 'Medium', 'High')", name="chk_responses_interest"),
        Index("ix_responses_survey_completed", "survey_id", "survey_completed_at"),
        Index("ix_responses_org_score", "organization_id", "score"),
    )


# ---------- Conversations (one per visitor/session) ----------
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # Your existing SID from the frontend
    sid: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # optional denormalized tracking
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    organization: Mapped[Organization] = relationship("Organization", back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        "Event", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "sid", name="uq_conversations_org_sid"),
    )


# ---------- Messages ----------
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant" | "staff"
    text: Mapped[str] = mapped_column(Text)
    # epoch seconds in your Pydantic schema => store as DateTime too
    ts_epoch: Mapped[int] = mapped_column(Integer)  # keep 1:1 with current API
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        CheckConstraint("role in ('user','assistant','staff')", name="chk_messages_role"),
        Index("ix_messages_conv_ts", "conversation_id", "ts_epoch"),
    )


# ---------- Leads (DEPRECATED - keeping for backward compatibility) ----------
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )

    # Link to conversation if you want
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )

    # Fields aligned with your Pydantic Lead model
    sid: Mapped[str] = mapped_column(String(64), index=True)  # store visitor sid
    name: Mapped[str] = mapped_column(String(160), default="")
    industry: Mapped[str] = mapped_column(String(120), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(60), default="awareness")
    compatibility: Mapped[bool] = mapped_column(Boolean, default=False)
    interest: Mapped[str] = mapped_column(String(16), default="Low")
    phone: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    adsExp: Mapped[bool] = mapped_column(Boolean, default=False)
    lastMessage: Mapped[str] = mapped_column(Text, default="")
    lastSeenSec: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    # Survey tracking
    survey_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    survey_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    survey_answers: Mapped[Optional[dict]] = mapped_column(JSON)  # {node_id: answer}
    survey_progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100 percentage
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="leads")
    conversation: Mapped[Optional[Conversation]] = relationship("Conversation")
    
    # Backward compatibility alias
    @property
    def client_id(self):
        return self.organization_id

    __table_args__ = (
        Index("ix_leads_org_stage", "organization_id", "stage"),
        Index("ix_leads_org_sid", "organization_id", "sid"),
    )


# ---------- Events (analytics stream) ----------
class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(80), index=True)  # e.g., "click_quick_reply"
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    ts_epoch: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="events")


# ---------- Live Help Sessions ----------
class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sid: Mapped[str] = mapped_column(String(64), index=True)
    manager_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    manager_display_name: Mapped[str] = mapped_column(String(120), default="")
    provider: Mapped[str] = mapped_column(String(32), default="livekit")
    status: Mapped[str] = mapped_column(String(20), default="preview")
    room_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    stage_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    live_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="live_sessions")

    __table_args__ = (
        CheckConstraint("status IN ('preview', 'live', 'ended', 'disconnected')", name="chk_live_sessions_status"),
        Index("ix_live_sessions_org_sid_created", "organization_id", "sid", "created_at"),
        Index("ix_live_sessions_org_status", "organization_id", "status"),
    )


# ---------- Organization Payment Settings ----------
class OrganizationPaymentSettings(Base):
    __tablename__ = "organization_payment_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="stripe")
    mode: Mapped[str] = mapped_column(String(32), default="stripe_connect_standard")
    payments_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    default_currency: Mapped[str] = mapped_column(String(8), default="EUR")

    stripe_account_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    stripe_connect_status: Mapped[str] = mapped_column(String(24), default="not_connected")
    stripe_onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_details_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_charges_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stripe_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stripe_publishable_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_scope: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stripe_livemode: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_oauth_state: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    stripe_last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="payment_settings")

    __table_args__ = (
        CheckConstraint("provider IN ('stripe')", name="chk_org_payment_settings_provider"),
        CheckConstraint("mode IN ('stripe_connect_standard')", name="chk_org_payment_settings_mode"),
        CheckConstraint("stripe_connect_status IN ('not_connected', 'pending', 'connected', 'restricted', 'error')", name="chk_org_payment_settings_status"),
    )


# ---------- Payment Requests ----------
class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sid: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    provider: Mapped[str] = mapped_column(String(32), default="mock")
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    provider_session_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    purpose: Mapped[str] = mapped_column(String(160), default="Payment request")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="sent")
    payment_url: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    provider_payload: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="payment_requests")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'sent', 'paid', 'failed', 'expired', 'cancelled')", name="chk_payment_requests_status"),
        CheckConstraint("amount_cents > 0", name="chk_payment_requests_amount_positive"),
        Index("ix_payment_requests_org_sid_created", "organization_id", "sid", "created_at"),
        Index("ix_payment_requests_org_status", "organization_id", "status"),
    )
