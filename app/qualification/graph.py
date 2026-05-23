from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from app.qualification.prompts import build_qualify_prompt, build_conversation_prompt, PROSTORAI_ROLE_CONTRACT, PROSTORAI_CAPABILITIES
from app.qualification.runtime_context import build_runtime_context, retrieve_knowledge
from app.qualification.state import QualificationGraphState, TurnDecision, TurnInterpretation
from app.services.llm_service import LLMService
from app.qualification.tools import GURS_TOOLS, execute_tool

try:
    from langgraph.graph import StateGraph, END
except Exception:  # pragma: no cover
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore


_QUALIFY_SYSTEM = "You analyze ProstorAI spatial assistance turns and return only valid JSON."


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
    spatial = state.get("spatial_context")
    profile = _prompt_profile(state)
    recent = (state.get("recent_messages", []) or [])[-6:]
    latest = state.get("latest_message", "")

    compact_spatial = json.dumps(spatial or {}, ensure_ascii=False, separators=(",", ":"))
    compact_profile = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    compact_msgs = json.dumps([{"r": m.get("role","user"), "t": m.get("text","")} for m in recent], ensure_ascii=False, separators=(",", ":"))

    system = (
        f"{PROSTORAI_ROLE_CONTRACT}\n\n"
        f"{PROSTORAI_CAPABILITIES}\n\n"
        f"SPATIAL_CONTEXT: {compact_spatial}\n"
        f"PROFILE: {compact_profile}\n"
        f"MESSAGES: {compact_msgs}\n"
    )
    user = json.dumps(latest, ensure_ascii=False)

    # Tool-calling loop — correct OpenAI pattern
    msgs = [{"role": "user", "content": user}]
    reply = ""
    for round_idx in range(4):
        # First 3 rounds: MUST use a tool. Last round: can answer.
        force = (round_idx < 3)
        resp = llm.call_with_tools(system, msgs, GURS_TOOLS, required=force)
        tcs = resp.get("tool_calls")
        if not tcs:
            reply = resp.get("text", "")
            break
        # Execute all tool calls from this round
        results = {}
        for tc in tcs:
            results[tc["id"]] = execute_tool(tc["name"], tc["args"])
        for tc in tcs:
            msgs.append({"role": "assistant", "content": None, "tool_calls": [{"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}]})
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": results[tc["id"]]})
    # Fallback: get JSON response if LLM didn't answer directly
    if not reply:
        reply = llm.call_json_response(system, msgs)
    if not reply:
        reply = "Pozdravljeni! Sem ProstorAI, vaš digitalni asistent za prostorske podatke Slovenije. Kako vam lahko pomagam?"

    used_llm = bool(reply)
    interpretation = TurnInterpretation(
        visitor_type="sales_prospect", preferred_language="sl",
        used_llm=used_llm, model_name=llm.model_name,
    )
    decision = TurnDecision(
        reply=reply, recommended_next_action="continue_conversation",
        qualification_band="warm", qualification_score=55, confidence_overall=0.5,
        used_llm=used_llm, model_name=llm.model_name,
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
    spatial_context: Optional[Dict[str, Any]] = None,
) -> QualificationGraphState:
    state: QualificationGraphState = {
        "qualifier": qualifier,
        "latest_message": latest_message,
        "recent_messages": recent_messages,
        "profile_before": profile_before,
        "spatial_context": spatial_context,
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
