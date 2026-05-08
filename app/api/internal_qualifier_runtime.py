from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.qualification.graph import run_qualification_graph
from app.qualification.state import TurnDecision, TurnInterpretation
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/internal/qualifier-runtime", tags=["internal-qualifier-runtime"])
llm_service = LLMService()


class QualifierRuntimeRequest(BaseModel):
    sid: str
    message: str
    qualifier: Dict[str, Any]
    recent_messages: List[Dict[str, str]] = Field(default_factory=list)
    existing_profile: Dict[str, Any] = Field(default_factory=dict)


class QualifierRuntimeResponse(BaseModel):
    reply: str
    profile: Dict[str, Any]
    field_confidence: Dict[str, float]
    qualification_score: int
    qualification_band: str
    confidence_overall: float
    reasoning: str
    recommended_next_action: str
    missing_fields: List[str]
    takeover_eligible: bool
    video_offer_eligible: bool
    model_name: Optional[str] = None


@router.post("/evaluate", response_model=QualifierRuntimeResponse)
def evaluate(payload: QualifierRuntimeRequest):
    qualifier = SimpleNamespace(**payload.qualifier)
    state = run_qualification_graph(
        llm=llm_service,
        qualifier=qualifier,
        latest_message=payload.message,
        recent_messages=payload.recent_messages,
        profile_before=payload.existing_profile,
    )

    interpretation: TurnInterpretation = state.get("interpretation") or TurnInterpretation()
    decision: TurnDecision = state.get("decision") or TurnDecision()
    profile = dict(interpretation.profile_after or payload.existing_profile or {})
    profile["visitor_type"] = interpretation.visitor_type or profile.get("visitor_type") or "unclear"
    profile["funnel_stage"] = decision.funnel_stage or profile.get("funnel_stage") or "business_context"
    profile["qualification_complete"] = bool(decision.qualification_complete)
    if interpretation.supporting_quotes:
        profile["supporting_quotes"] = interpretation.supporting_quotes

    reply = (decision.reply or fallback_reply(payload.message)).strip()
    reasoning = combine_reasoning(interpretation.reasoning_hint, decision.reasoning_hint)

    return QualifierRuntimeResponse(
        reply=reply,
        profile=profile,
        field_confidence={k: float(v) for k, v in interpretation.field_confidence.items()},
        qualification_score=int(decision.qualification_score or 0),
        qualification_band=decision.qualification_band or "cold",
        confidence_overall=float(decision.confidence_overall or interpretation.confidence_overall or 0.0),
        reasoning=reasoning,
        recommended_next_action=decision.recommended_next_action or "ask_clarifying_question",
        missing_fields=list(decision.missing_fields or []),
        takeover_eligible=bool(decision.takeover_eligible),
        video_offer_eligible=bool(decision.video_offer_eligible),
        model_name=decision.model_name or interpretation.model_name or llm_service.model_name,
    )


def combine_reasoning(interpretation_reason: str, decision_reason: str) -> str:
    parts = [p.strip() for p in [interpretation_reason, decision_reason] if p and p.strip()]
    return "; ".join(dict.fromkeys(parts)) or "Qualification updated"


def fallback_reply(latest_message: str) -> str:
    lowered = (latest_message or "").lower()
    if any(token in lowered for token in [" kako ", " ali ", " sem ", " prodajam", " podjet", " strank", " povpraš"]):
        return "Na kratko mi opišite vaš posel in kako danes dobivate stranke, pa preverim, kako vam lahko ACE e-Counter pomaga."
    return "Briefly describe your business and how customers reach you today, and I’ll check how ACE e-Counter could help."
