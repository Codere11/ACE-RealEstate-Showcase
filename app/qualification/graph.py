from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from app.qualification.prompts import build_analysis_prompt, build_writer_prompt
from app.qualification.runtime_context import build_runtime_context, retrieve_knowledge
from app.qualification.state import QualificationGraphState, TurnDecision, TurnInterpretation
from app.services.llm_service import LLMService

try:
    from langgraph.graph import StateGraph, END
except Exception:  # pragma: no cover
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore


_ANALYZE_SYSTEM = "You analyze ACE e-Counter qualification turns. Return only valid JSON."
_WRITE_SYSTEM = "You write the next ACE e-Counter reply. Return plain text only."


def _load_runtime_context(state: QualificationGraphState) -> QualificationGraphState:
    state["runtime_context"] = build_runtime_context(state["qualifier"])
    return state


def _retrieve_knowledge(state: QualificationGraphState) -> QualificationGraphState:
    state["retrieved_knowledge"] = retrieve_knowledge(
        state.get("runtime_context", {}) or {},
        state.get("recent_messages", []) or [],
        limit=6,
    )
    return state


def _prompt_runtime_context(state: QualificationGraphState) -> Dict[str, Any]:
    ctx = dict(state.get("runtime_context", {}) or {})
    ctx.pop("knowledge_snippets", None)
    return ctx


def _analyze_turn(llm: LLMService, state: QualificationGraphState) -> QualificationGraphState:
    prompt = build_analysis_prompt(
        runtime_context=_prompt_runtime_context(state),
        knowledge_context=state.get("retrieved_knowledge", []) or [],
        existing_profile=state.get("profile_before", {}) or {},
        recent_messages=state.get("recent_messages", []) or [],
        latest_message=state.get("latest_message", ""),
    )
    data = llm.call_json(_ANALYZE_SYSTEM, prompt)
    profile_after = dict(state.get("profile_before", {}) or {})
    profile_after.update(dict(data.get("profile_after") or {}))
    interpretation = TurnInterpretation(
        visitor_type=str(data.get("visitor_type") or "unclear"),
        preferred_language=str(data.get("preferred_language") or "en"),
        profile_after=profile_after,
        field_confidence={k: float(v) for k, v in dict(data.get("field_confidence") or {}).items() if _is_number(v)},
        confidence_overall=_clamp(data.get("confidence_overall"), 0.0),
        supporting_quotes=[str(x) for x in (data.get("supporting_quotes") or []) if str(x).strip()][:4],
        reasoning_hint=str(data.get("reasoning_hint") or "").strip()[:400],
        used_llm=bool(data),
        model_name=llm.model_name,
    )
    interpretation.profile_after["visitor_type"] = interpretation.visitor_type
    interpretation.profile_after["preferred_language"] = interpretation.preferred_language
    if interpretation.supporting_quotes:
        interpretation.profile_after["supporting_quotes"] = interpretation.supporting_quotes

    decision = TurnDecision(
        reply="",
        recommended_next_action=str(data.get("recommended_next_action") or "ask_clarifying_question"),
        suggested_reply_strategy=str(data.get("suggested_reply_strategy") or "ask_single_question"),
        next_best_question=str(data.get("next_best_question") or "").strip(),
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

    state["interpretation"] = interpretation
    state["decision"] = decision
    return state


def _write_reply(llm: LLMService, state: QualificationGraphState) -> QualificationGraphState:
    interpretation = state.get("interpretation") or TurnInterpretation()
    decision = state.get("decision") or TurnDecision()
    analysis = {
        **asdict(interpretation),
        **asdict(decision),
    }
    prompt = build_writer_prompt(
        runtime_context=_prompt_runtime_context(state),
        knowledge_context=state.get("retrieved_knowledge", []) or [],
        recent_messages=state.get("recent_messages", []) or [],
        latest_message=state.get("latest_message", ""),
        analysis=analysis,
    )
    decision.reply = llm.call_text(_WRITE_SYSTEM, prompt, temperature=0.2).strip()
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
        state = _load_runtime_context(state)
        state = _retrieve_knowledge(state)
        state = _analyze_turn(llm, state)
        state = _write_reply(llm, state)
        return state

    graph = StateGraph(QualificationGraphState)
    graph.add_node("load_runtime_context", _load_runtime_context)
    graph.add_node("retrieve_knowledge", _retrieve_knowledge)
    graph.add_node("analyze_turn", lambda s: _analyze_turn(llm, s))
    graph.add_node("write_reply", lambda s: _write_reply(llm, s))
    graph.set_entry_point("load_runtime_context")
    graph.add_edge("load_runtime_context", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "analyze_turn")
    graph.add_edge("analyze_turn", "write_reply")
    graph.add_edge("write_reply", END)
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
