from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from app.qualification.prompts import build_decide_prompt, build_interpret_prompt
from app.qualification.state import QualificationGraphState, TurnDecision, TurnInterpretation
from app.services.llm_service import LLMService

try:
    from langgraph.graph import StateGraph, END
except Exception:  # pragma: no cover
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore


_INTERPRET_SYSTEM = "You interpret ACE e-Counter qualification turns. Return only valid JSON."
_DECIDE_SYSTEM = "You decide the next ACE e-Counter qualification step. Return only valid JSON."


def _interpret_turn(llm: LLMService, state: QualificationGraphState) -> QualificationGraphState:
    qualifier = state["qualifier"]
    prompt = build_interpret_prompt(
        system_prompt=qualifier.system_prompt,
        goal_definition=qualifier.goal_definition,
        existing_profile=state.get("profile_before", {}) or {},
        recent_messages=state.get("recent_messages", []),
    )
    data = llm.call_json(_INTERPRET_SYSTEM, prompt)
    interpretation = TurnInterpretation(
        visitor_type=str(data.get("visitor_type") or "unclear"),
        profile_after=dict(data.get("profile_after") or state.get("profile_before", {}) or {}),
        field_confidence={k: float(v) for k, v in dict(data.get("field_confidence") or {}).items() if _is_number(v)},
        confidence_overall=_clamp(data.get("confidence_overall"), 0.0),
        supporting_quotes=[str(x) for x in (data.get("supporting_quotes") or []) if str(x).strip()][:3],
        reasoning_hint=str(data.get("reasoning_hint") or "").strip()[:400],
        used_llm=bool(data),
        model_name=llm.model_name,
    )
    if interpretation.profile_after:
        interpretation.profile_after["visitor_type"] = interpretation.visitor_type
        if interpretation.supporting_quotes:
            interpretation.profile_after["supporting_quotes"] = interpretation.supporting_quotes
    state["interpretation"] = interpretation
    return state


def _decide_next_step(llm: LLMService, state: QualificationGraphState) -> QualificationGraphState:
    qualifier = state["qualifier"]
    interpretation = state.get("interpretation") or TurnInterpretation()
    prompt = build_decide_prompt(
        assistant_style=qualifier.assistant_style,
        required_fields=list(qualifier.required_fields or []),
        latest_message=state.get("latest_message", ""),
        recent_messages=state.get("recent_messages", []),
        interpretation=asdict(interpretation),
    )
    data = llm.call_json(_DECIDE_SYSTEM, prompt)
    decision = TurnDecision(
        reply=str(data.get("reply") or "").strip(),
        recommended_next_action=str(data.get("recommended_next_action") or "ask_clarifying_question"),
        funnel_stage=str(data.get("funnel_stage") or "business_context"),
        qualification_complete=bool(data.get("qualification_complete")),
        missing_fields=[str(x) for x in (data.get("missing_fields") or []) if str(x).strip()],
        qualification_score=_clamp_int(data.get("qualification_score"), 0),
        qualification_band=str(data.get("qualification_band") or "cold"),
        takeover_eligible=bool(data.get("takeover_eligible")),
        video_offer_eligible=bool(data.get("video_offer_eligible")),
        confidence_overall=_clamp(data.get("confidence_overall"), interpretation.confidence_overall),
        reasoning_hint=str(data.get("reasoning_hint") or "").strip()[:400],
        used_llm=bool(data),
        model_name=llm.model_name,
    )
    state["decision"] = decision
    return state


def run_qualification_graph(
    *,
    llm: LLMService,
    qualifier: Any,
    latest_message: str,
    recent_messages: List[Dict[str, str]],
    profile_before: Dict[str, Any],
) -> QualificationGraphState:
    state: QualificationGraphState = {
        "qualifier": qualifier,
        "latest_message": latest_message,
        "recent_messages": recent_messages,
        "profile_before": profile_before,
    }

    if StateGraph is None:
        state = _interpret_turn(llm, state)
        state = _decide_next_step(llm, state)
        return state

    graph = StateGraph(QualificationGraphState)
    graph.add_node("interpret_turn", lambda s: _interpret_turn(llm, s))
    graph.add_node("decide_next_step", lambda s: _decide_next_step(llm, s))
    graph.set_entry_point("interpret_turn")
    graph.add_edge("interpret_turn", "decide_next_step")
    graph.add_edge("decide_next_step", END)
    return graph.compile().invoke(state)


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def _clamp(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _clamp_int(value: Any, default: int) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return default
