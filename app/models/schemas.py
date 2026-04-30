# app/models/schemas.py
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field


# ---------- Organization Schemas ----------
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    slug: str = Field(..., min_length=1, max_length=80)
    subdomain: Optional[str] = Field(None, max_length=160)
    active: bool = True


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    slug: Optional[str] = Field(None, min_length=1, max_length=80)
    subdomain: Optional[str] = Field(None, max_length=160)
    active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True  # For Pydantic v1 compatibility
        from_attributes = True


# ---------- User Schemas ----------
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")  # Basic email validation
    role: Literal["org_admin", "org_user"] = "org_user"
    is_active: bool = True
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    organization_id: int


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=80)
    email: Optional[str] = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[Literal["org_admin", "org_user"]] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: int
    organization_id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        orm_mode = True  # For Pydantic v1 compatibility
        from_attributes = True


# ---------- Survey Schemas ----------
class SurveyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    slug: str = Field(..., min_length=1, max_length=80)
    survey_type: Literal["regular", "ab_test"] = "regular"
    status: Literal["draft", "live", "archived"] = "draft"


class SurveyCreate(SurveyBase):
    organization_id: int
    flow_json: Optional[Dict[str, Any]] = None
    variant_a_flow: Optional[Dict[str, Any]] = None
    variant_b_flow: Optional[Dict[str, Any]] = None


class SurveyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    slug: Optional[str] = Field(None, min_length=1, max_length=80)
    survey_type: Optional[Literal["regular", "ab_test"]] = None
    status: Optional[Literal["draft", "live", "archived"]] = None
    flow_json: Optional[Dict[str, Any]] = None
    variant_a_flow: Optional[Dict[str, Any]] = None
    variant_b_flow: Optional[Dict[str, Any]] = None


class SurveyResponse(SurveyBase):
    id: int
    organization_id: int
    flow_json: Optional[Dict[str, Any]] = None
    variant_a_flow: Optional[Dict[str, Any]] = None
    variant_b_flow: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True  # For Pydantic v1 compatibility
        from_attributes = True


# ---------- Qualifier Schemas ----------
class QualifierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    slug: str = Field(..., min_length=1, max_length=80)
    status: Literal["draft", "live", "archived"] = "draft"
    system_prompt: str = ""
    assistant_style: str = "friendly, concise, consultative"
    goal_definition: str = ""
    field_schema: Optional[Dict[str, Any]] = None
    required_fields: Optional[List[str]] = None
    scoring_rules: Optional[Dict[str, Any]] = None
    band_thresholds: Optional[Dict[str, Any]] = None
    confidence_thresholds: Optional[Dict[str, Any]] = None
    takeover_rules: Optional[Dict[str, Any]] = None
    video_offer_rules: Optional[Dict[str, Any]] = None
    rag_enabled: bool = False
    knowledge_source_ids: Optional[List[Any]] = None
    max_clarifying_questions: int = Field(default=3, ge=0, le=20)
    contact_capture_policy: str = Field(default="when_high_intent_or_explicit", max_length=64)
    version: int = Field(default=1, ge=1)
    version_notes: str = ""


class QualifierCreate(QualifierBase):
    organization_id: int


class QualifierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    slug: Optional[str] = Field(None, min_length=1, max_length=80)
    status: Optional[Literal["draft", "live", "archived"]] = None
    system_prompt: Optional[str] = None
    assistant_style: Optional[str] = None
    goal_definition: Optional[str] = None
    field_schema: Optional[Dict[str, Any]] = None
    required_fields: Optional[List[str]] = None
    scoring_rules: Optional[Dict[str, Any]] = None
    band_thresholds: Optional[Dict[str, Any]] = None
    confidence_thresholds: Optional[Dict[str, Any]] = None
    takeover_rules: Optional[Dict[str, Any]] = None
    video_offer_rules: Optional[Dict[str, Any]] = None
    rag_enabled: Optional[bool] = None
    knowledge_source_ids: Optional[List[Any]] = None
    max_clarifying_questions: Optional[int] = Field(default=None, ge=0, le=20)
    contact_capture_policy: Optional[str] = Field(default=None, max_length=64)
    version: Optional[int] = Field(default=None, ge=1)
    version_notes: Optional[str] = None


class QualifierResponse(QualifierBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True


class LeadProfileResponse(BaseModel):
    id: int
    organization_id: int
    sid: str
    qualifier_id: Optional[int] = None
    qualifier_version: int
    profile: Optional[Dict[str, Any]] = None
    field_confidence: Optional[Dict[str, float]] = None
    qualification_score: int
    qualification_band: Literal["hot", "warm", "cold"]
    confidence_overall: float
    reasoning: str = ""
    recommended_next_action: str = ""
    missing_fields: Optional[List[str]] = None
    takeover_eligible: bool = False
    video_offer_eligible: bool = False
    last_qualified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class QualifierRunResponse(BaseModel):
    id: int
    organization_id: int
    sid: str
    qualifier_id: Optional[int] = None
    qualifier_version: int
    trigger: str
    input_message_ids: Optional[List[Any]] = None
    input_excerpt: str = ""
    output_profile_patch: Optional[Dict[str, Any]] = None
    score_before: Optional[int] = None
    score_after: Optional[int] = None
    band_before: Optional[Literal["hot", "warm", "cold"]] = None
    band_after: Optional[Literal["hot", "warm", "cold"]] = None
    confidence_overall: float
    reasoning: str = ""
    takeover_eligible: bool = False
    video_offer_eligible: bool = False
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class SurveyStats(BaseModel):
    """Statistics for a survey"""
    survey_id: int
    total_responses: int
    completed_responses: int
    avg_score: float
    avg_completion_time_minutes: Optional[float] = None
    # A/B test specific
    variant_a_responses: Optional[int] = None
    variant_b_responses: Optional[int] = None
    variant_a_avg_score: Optional[float] = None
    variant_b_avg_score: Optional[float] = None


# ---------- Survey Response Schemas ----------
class SurveyResponseBase(BaseModel):
    name: str = Field(default="", max_length=160)
    email: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=60)
    survey_answers: Optional[Dict[str, Any]] = None
    score: int = Field(default=0, ge=0, le=100)
    interest: Literal["Low", "Medium", "High"] = "Low"
    notes: str = ""


class SurveyResponseCreate(BaseModel):
    survey_id: int
    sid: str
    variant: Optional[Literal["a", "b"]] = None
    survey_answers: Dict[str, Any] = {}
    name: str = ""
    email: str = ""
    phone: str = ""


class SurveyResponseUpdate(BaseModel):
    survey_answers: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    interest: Optional[Literal["Low", "Medium", "High"]] = None
    survey_progress: Optional[int] = Field(None, ge=0, le=100)
    survey_completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class SurveyResponseDetail(SurveyResponseBase):
    id: int
    survey_id: int
    organization_id: int
    sid: str
    variant: Optional[Literal["a", "b"]] = None
    survey_started_at: datetime
    survey_completed_at: Optional[datetime] = None
    survey_progress: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True  # For Pydantic v1 compatibility
        from_attributes = True


# ---------- Authentication Schemas ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    user_id: int
    organization_id: int
    role: Literal["org_admin", "org_user"]


# ---------- Legacy Lead Schema (backward compatibility) ----------
class Lead(BaseModel):
    """Legacy Lead model for backward compatibility"""
    sid: str
    name: str = ""
    industry: str = ""
    score: int = 0
    stage: str = "awareness"
    compatibility: bool = False
    interest: str = "Low"
    phone: bool = False
    email: bool = False
    adsExp: bool = False
    lastMessage: str = ""
    lastSeenSec: int = 0
    notes: str = ""
    survey_answers: Optional[Dict[str, Any]] = None
    survey_progress: int = 0
    
    class Config:
        orm_mode = True  # For Pydantic v1 compatibility
        from_attributes = True
