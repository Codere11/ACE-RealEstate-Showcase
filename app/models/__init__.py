# Make `from app.models import User, Tenant, ConversationFlow` work
from .core import Tenant, User, ConversationFlow  # re-export

# Import ORM models so SQLAlchemy metadata is populated during bootstrap
from .orm import (  # noqa: F401
    Organization,
    Survey,
    SurveyResponse,
    Conversation,
    Message,
    Lead,
    Event,
    Qualifier,
    LeadProfile,
    QualifierRun,
    PaymentRequest,
    OrganizationPaymentSettings,
)

# If someone imports Base from here, forward it (optional convenience)
try:
    from app.services.db import Base  # not required, but handy
except Exception:
    Base = None  # avoid import errors during tooling
