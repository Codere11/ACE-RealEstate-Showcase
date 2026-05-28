from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict


@dataclass
class TurnInterpretation:
    visitor_type: str = "unclear"
    preferred_language: str = "en"
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
    recommended_next_action: str = "continue_conversation"
    suggested_reply_strategy: str = "ask_single_question"
    next_best_question: str = ""
    funnel_stage: str = "greeting"
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


# ── Conversation stages for routing ──
ConversationStage = Literal[
    "greeting",
    "discovery",
    "availability",
    "booking",
    "addon",         # user wants to add an add-on to existing booking
    "handoff",
    "idle",
]


class QualificationGraphState(TypedDict, total=False):
    qualifier: Any
    latest_message: str
    recent_messages: List[Dict[str, str]]
    profile_before: Dict[str, Any]
    spatial_context: Optional[Dict[str, Any]]

    # ── Conversation state (prevents repetition) ──
    conversation_stage: ConversationStage
    hours_mentioned: bool         # has the AI already told open/closed status?
    services_presented: bool      # has the AI already listed all services?
    service_interest: str         # which service customer is interested in (if any)
    booking_date: str             # date customer wants to book
    booking_time: str             # time customer selected
    booking_confirmed: bool       # was a booking confirmed this turn?

    # ── Internal graph state (added by call_tools / auto_book nodes) ──
    tool_results: Dict[str, str]
    tool_calls: List[Dict[str, Any]]
    tool_messages: List[Dict[str, Any]]
    system_prompt: str
    contact_missing: bool
    latest_json: str
    booking_extracted: Optional[Dict[str, str]]
    auto_book_reply: str          # set by auto_book node for generate_reply
    salon_closed_request: bool    # set when staff requested but salon closed

    # ── Existing pipeline fields ──
    runtime_context: Dict[str, Any]
    retrieved_knowledge: List[str]
    interpretation: TurnInterpretation
    decision: TurnDecision
