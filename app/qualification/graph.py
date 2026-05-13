from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.qualification.prompts import build_qualify_prompt
from app.qualification.runtime_context import build_runtime_context, retrieve_knowledge
from app.qualification.state import QualificationGraphState, TurnDecision, TurnInterpretation
from app.services.llm_service import LLMService

try:
    from langgraph.graph import StateGraph, END
except Exception:  # pragma: no cover
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore


_QUALIFY_SYSTEM = "You analyze ACE e-Counter qualification turns and return only valid JSON."


def _load_runtime_context(state: QualificationGraphState) -> QualificationGraphState:
    state["runtime_context"] = build_runtime_context(state["qualifier"])
    return state


def _retrieve_knowledge(state: QualificationGraphState) -> QualificationGraphState:
    state["retrieved_knowledge"] = retrieve_knowledge(
        state.get("runtime_context", {}) or {},
        state.get("recent_messages", []) or [],
        limit=3,
    )
    return state


def _prompt_runtime_context(state: QualificationGraphState) -> Dict[str, Any]:
    ctx = dict(state.get("runtime_context", {}) or {})
    return {
        "static_prompt_block": str(ctx.get("static_prompt_block") or "").strip(),
        "max_clarifying_questions": int(ctx.get("max_clarifying_questions") or 3),
    }


def _prompt_profile(state: QualificationGraphState) -> Dict[str, Any]:
    profile = dict(state.get("profile_before", {}) or {})
    keep_keys = [
        "visitor_type",
        "preferred_language",
        "business_type",
        "business_model",
        "customer_source",
        "sales_motion",
        "growth_constraint",
        "pain_points",
        "desired_outcome",
        "use_case_fit",
        "fit_status",
        "supporting_quotes",
        "funnel_stage",
    ]
    return {key: profile.get(key) for key in keep_keys if profile.get(key) not in (None, "", [], {})}


def _get(data: Dict[str, Any], long_key: str, short_key: str, default=None):
    if short_key in data:
        return data.get(short_key)
    return data.get(long_key, default)


def _qualify_and_write(llm: LLMService, state: QualificationGraphState) -> QualificationGraphState:
    prompt = build_qualify_prompt(
        runtime_context=_prompt_runtime_context(state),
        knowledge_context=state.get("retrieved_knowledge", []) or [],
        existing_profile=_prompt_profile(state),
        recent_messages=(state.get("recent_messages", []) or [])[-4:],
        latest_message=state.get("latest_message", ""),
    )
    data = llm.call_json(_QUALIFY_SYSTEM, prompt)
    profile_after = dict(state.get("profile_before", {}) or {})
    profile_after.update(dict(_get(data, "profile_after", "p", {}) or {}))
    interpretation = TurnInterpretation(
        visitor_type=str(_get(data, "visitor_type", "vt", "unclear") or "unclear"),
        preferred_language=str(_get(data, "preferred_language", "lang", "en") or "en"),
        profile_after=profile_after,
        field_confidence={k: float(v) for k, v in dict(_get(data, "field_confidence", "fc", {}) or {}).items() if _is_number(v)},
        confidence_overall=_clamp(_get(data, "confidence_overall", "co", 0.0), 0.0),
        supporting_quotes=[str(x) for x in (_get(data, "supporting_quotes", "sq", []) or []) if str(x).strip()][:4],
        reasoning_hint=str(_get(data, "reasoning_hint", "why", "") or "").strip()[:400],
        used_llm=bool(data),
        model_name=llm.model_name,
    )
    interpretation.profile_after["visitor_type"] = interpretation.visitor_type
    interpretation.profile_after["preferred_language"] = interpretation.preferred_language
    if interpretation.supporting_quotes:
        interpretation.profile_after["supporting_quotes"] = interpretation.supporting_quotes

    qualification_score, qualification_band = _normalize_score_and_band(
        data,
        runtime_context=state.get("runtime_context", {}) or {},
        fit_status=str(interpretation.profile_after.get("fit_status") or "unknown"),
        recommended_next_action=str(_get(data, "recommended_next_action", "act", "ask_clarifying_question") or "ask_clarifying_question"),
    )
    decision = TurnDecision(
        reply=str(_get(data, "reply", "rep", "") or "").strip(),
        recommended_next_action=str(_get(data, "recommended_next_action", "act", "ask_clarifying_question") or "ask_clarifying_question"),
        suggested_reply_strategy=str(_get(data, "suggested_reply_strategy", "strat", "ask_single_question") or "ask_single_question"),
        next_best_question=str(_get(data, "next_best_question", "q", "") or "").strip(),
        funnel_stage=str(_get(data, "funnel_stage", "stage", "business_context") or "business_context"),
        qualification_complete=bool(_get(data, "qualification_complete", "done", False)),
        missing_fields=[str(x) for x in (_get(data, "missing_fields", "miss", []) or []) if str(x).strip()],
        qualification_score=qualification_score,
        qualification_band=qualification_band,
        takeover_eligible=bool(_get(data, "takeover_eligible", "to", False)),
        video_offer_eligible=bool(_get(data, "video_offer_eligible", "vo", False)),
        confidence_overall=_clamp(_get(data, "confidence_overall", "co", interpretation.confidence_overall), interpretation.confidence_overall),
        reasoning_hint=str(_get(data, "reasoning_hint", "why", "") or "").strip()[:400],
        used_llm=bool(data),
        model_name=llm.model_name,
    )

    decision.reply = _normalize_reply(
        decision.reply,
        recommended_next_action=decision.recommended_next_action,
        next_best_question=decision.next_best_question,
    )
    state["interpretation"] = interpretation
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
        state = _qualify_and_write(llm, state)
        return state

    graph = StateGraph(QualificationGraphState)
    graph.add_node("load_runtime_context", _load_runtime_context)
    graph.add_node("retrieve_knowledge", _retrieve_knowledge)
    graph.add_node("qualify_and_write", lambda s: _qualify_and_write(llm, s))
    graph.set_entry_point("load_runtime_context")
    graph.add_edge("load_runtime_context", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "qualify_and_write")
    graph.add_edge("qualify_and_write", END)
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


def _normalize_reply(reply: str, *, recommended_next_action: str, next_best_question: str) -> str:
    text = (reply or "").strip()
    if text:
        return text
    if recommended_next_action == "route_support":
        return "This sounds like an existing support issue, so I’m routing it to the support team now."
    if next_best_question:
        return next_best_question.strip()
    return "Tell me a bit more about your current inbound lead process, and I’ll map how ACE would fit."


def _normalize_score_and_band(data: Dict[str, Any], *, runtime_context: Dict[str, Any], fit_status: str, recommended_next_action: str) -> Tuple[int, str]:
    band_thresholds = dict(runtime_context.get("band_thresholds") or {})
    hot_min = _clamp_int(band_thresholds.get("hot_min"), 70)
    warm_min = _clamp_int(band_thresholds.get("warm_min"), 40)
    if hot_min < warm_min:
        hot_min, warm_min = warm_min, hot_min

    raw_score = _clamp_int(_get(data, "qualification_score", "score", -1), -1)
    raw_band = str(_get(data, "qualification_band", "band", "") or "").strip().lower()

    score = raw_score
    band = raw_band if raw_band in {"cold", "warm", "hot"} else ""

    if score < 0:
        score = 0

    if score == 0 and band in {"warm", "hot"}:
        score = warm_min + 5 if band == "warm" else max(hot_min + 5, 80)
    elif score == 0 and fit_status == "high":
        score = max(warm_min + 5, 55)
    elif score == 0 and fit_status == "medium":
        score = max(warm_min, 45)

    if not band:
        if score >= hot_min:
            band = "hot"
        elif score >= warm_min:
            band = "warm"
        else:
            band = "cold"

    if band == "hot" and score < hot_min:
        score = max(score, hot_min)
    elif band == "warm" and score < warm_min:
        score = max(score, warm_min)
    elif band == "cold" and score >= warm_min and fit_status != "high":
        band = "warm"

    if recommended_next_action in {"offer_human_takeover"} and score < hot_min:
        score = max(score, hot_min)
        band = "hot"

    return max(0, min(100, score)), band
