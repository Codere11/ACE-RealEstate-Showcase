from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


@dataclass
class TurnInterpretation:
    visitor_type: str = "unclear"
    profile_after: Dict[str, Any] = field(default_factory=dict)
    field_confidence: Dict[str, float] = field(default_factory=dict)
    confidence_overall: float = 0.0
    supporting_quotes: List[str] = field(default_factory=list)
    reasoning_hint: str = ""
    used_llm: bool = False
    model_name: Optional[str] = None


@dataclass
class TurnDecision:
    reply: str = ""
    recommended_next_action: str = "ask_clarifying_question"
    funnel_stage: str = "business_context"
    qualification_complete: bool = False
    missing_fields: List[str] = field(default_factory=list)
    qualification_score: int = 0
    qualification_band: str = "cold"
    takeover_eligible: bool = False
    video_offer_eligible: bool = False
    confidence_overall: float = 0.0
    reasoning_hint: str = ""
    used_llm: bool = False
    model_name: Optional[str] = None


class QualificationGraphState(TypedDict, total=False):
    qualifier: Any
    latest_message: str
    recent_messages: List[Dict[str, str]]
    profile_before: Dict[str, Any]
    interpretation: TurnInterpretation
    decision: TurnDecision
