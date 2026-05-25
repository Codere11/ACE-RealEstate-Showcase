from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum, uuid

def new_sid(): return "sid_" + uuid.uuid4().hex[:12]

class UserRole(str, enum.Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    ORG_ADMIN = "ORG_ADMIN"
    ORG_USER = "ORG_USER"

class LeadStatus(str, enum.Enum):
    SURVEY = "SURVEY"
    OPEN_CHAT = "OPEN_CHAT"
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"
    CLOSED = "CLOSED"

class ConvRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    STAFF = "staff"

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(160), nullable=False)
    slug = Column(String(80), nullable=False, unique=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    username = Column(String(80), nullable=False, unique=True)
    email = Column(String(160), nullable=False)
    password_hash = Column(String(255), nullable=False)
    visible_password = Column(String(80), nullable=True)  # dev only
    role = Column(String(20), nullable=False, default="ORG_USER")
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    organization = relationship("Organization")

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    sid = Column(String(64), nullable=False)
    status = Column(SAEnum(LeadStatus), nullable=False, default=LeadStatus.OPEN_CHAT)
    takeover_active = Column(Boolean, default=False, nullable=False)
    staff_requested = Column(Boolean, default=False, nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    display_name = Column(String(160), nullable=True)
    last_message_preview = Column(Text, nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    qualification_score = Column(Integer, nullable=True)
    qualification_band = Column("qualification_band", String(20), nullable=True)
    confidence_overall = Column("confidence_overall", Integer, nullable=True)
    qualifier_profile = Column("qualifier_profile", JSON, nullable=True)
    qualifier_missing_fields = Column("qualifier_missing_fields", JSON, nullable=True)
    qualification_reasoning = Column("qualification_reasoning", Text, nullable=True)
    takeover_eligible = Column(Boolean, default=False, nullable=False)
    video_offer_eligible = Column(Boolean, default=False, nullable=False)
    survey_progress = Column(Integer, default=0, nullable=False)
    phone = Column(String(30), nullable=True)
    email = Column(String(160), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    organization = relationship("Organization")

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    role = Column(SAEnum(ConvRole), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    lead = relationship("Lead")

class LeadEvent(Base):
    __tablename__ = "lead_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    sid = Column(String(64), nullable=False)
    event_type = Column(String(80), nullable=False)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Qualifier(Base):
    __tablename__ = "qualifiers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(160), nullable=False)
    slug = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    system_prompt = Column(Text, nullable=False, default="")
    assistant_style = Column(String(255), nullable=False, default="friendly, concise, consultative")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    organization = relationship("Organization")

async def init_db():
    from database import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
