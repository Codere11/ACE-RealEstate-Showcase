from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.qualification.prompts import build_classify_prompt, build_node_prompt
from app.qualification.runtime_context import build_runtime_context, retrieve_knowledge
from app.qualification.state import (
    QualificationGraphState,
    TurnDecision,
    TurnInterpretation,
    ConversationStage,
)
from app.services.llm_service import LLMService
from app.qualification.tools import SALON_TOOLS, execute_tool

try:
    from langgraph.graph import StateGraph, END
except Exception:
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore


# ── Graph nodes ──

def _classify_intent(state: QualificationGraphState) -> QualificationGraphState:
    """Determine what the customer wants RIGHT NOW."""
    latest = state.get("latest_message", "").strip()
    recent = state.get("recent_messages", []) or []
    existing_stage = state.get("conversation_stage", "")

    # Fast-path: single-word greetings mid-conversation = idle
    lowered = latest.lower()
    greeting_words = {"dober dan", "zdravo", "živjo", "pozdravljeni", "pozdravljena",
                       "dober večer", "dober dan!", "živjo!", "hej", "oj", "hi", "hello"}
    is_just_greeting = lowered in greeting_words or (len(lowered.split()) <= 2 and any(g in lowered for g in ["dober", "zdravo", "živjo", "pozdrav", "hej", "oj", "hi"]))

    if existing_stage and existing_stage != "greeting" and is_just_greeting:
        state["conversation_stage"] = "idle"
        return state

    # Use LLM to classify for longer messages
    llm = LLMService()
    if llm.is_available() and latest:
        prompt = build_classify_prompt(latest, recent)
        result = llm.call_json(prompt, latest)
        stage: ConversationStage = result.get("stage", "greeting") if isinstance(result, dict) else "greeting"
    else:
        stage = "greeting"

    # If we're past greeting and LLM still says greeting, check if it's really just a greeting word
    if existing_stage and stage == "greeting" and existing_stage != "greeting":
        stage = existing_stage  # keep previous stage — context carries forward
    # If we're in availability and user gives contact/confirmation, stay in availability
    if existing_stage in ("availability", "booking") and stage in ("greeting", "idle", "discovery"):
        stage = existing_stage
    # If first-ever message is a greeting word, that's a proper greeting
    elif not existing_stage and is_just_greeting:
        stage = "greeting"
    # If we're in greeting stage and message is just another greeting — stay idle
    elif existing_stage == "greeting" and is_just_greeting:
        stage = "idle"

    state["conversation_stage"] = stage
    return state


def _route_by_stage(state: QualificationGraphState) -> str:
    stage = state.get("conversation_stage", "greeting")
    # Map to node names
    return stage


def _greeting_node(state: QualificationGraphState) -> QualificationGraphState:
    return _reply_for_stage(state, "greeting")


def _discovery_node(state: QualificationGraphState) -> QualificationGraphState:
    return _reply_for_stage(state, "discovery")


def _availability_node(state: QualificationGraphState) -> QualificationGraphState:
    return _reply_for_stage(state, "availability")


def _booking_node(state: QualificationGraphState) -> QualificationGraphState:
    return _reply_for_stage(state, "booking")


def _handoff_node(state: QualificationGraphState) -> QualificationGraphState:
    return _reply_for_stage(state, "handoff")


def _idle_node(state: QualificationGraphState) -> QualificationGraphState:
    return _reply_for_stage(state, "idle")


def _reply_for_stage(state: QualificationGraphState, stage: str) -> QualificationGraphState:
    llm = LLMService()
    latest = state.get("latest_message", "")
    recent = (state.get("recent_messages", []) or [])[-6:]
    hours_mentioned = state.get("hours_mentioned", False)
    services_presented = state.get("services_presented", False)

    # Get salon state from tools
    salon_state = execute_tool("salon_get_context", {})

    state_json = salon_state
    messages_json = json.dumps(
        [{"r": m.get("role", "user"), "t": m.get("text", "")} for m in recent],
        ensure_ascii=False,
    )
    latest_json = json.dumps(latest, ensure_ascii=False)

    system = build_node_prompt(
        stage,
        hours_mentioned=hours_mentioned,
        services_presented=services_presented,
        state_json=state_json,
        messages_json=messages_json,
        latest_json=latest_json,
    )

    # Tool-calling: availability & booking must call tools; others can optionally
    needs_tools = stage in ("greeting", "discovery", "availability", "booking", "handoff")
    force_tools = stage in ("availability", "booking")
    msgs = [{"role": "user", "content": latest_json}]
    reply = ""

    # Deterministic contact check for booking stages
    if stage in ("availability", "booking"):
        contact = json.loads(execute_tool("salon_check_contact", {}))
        if not contact.get("ok"):
            system += "\n\nPOZOR: Stranka NIMA kontaktnih podatkov. Vljudno prosi za telefonsko ali email PREDEN rezerviraš. NE kaži terminov dokler ne dobiš kontakta. Ne kliči salon_book_appointment dokler nimaš kontakta."

    if needs_tools and llm.is_available():
        resp = llm.call_with_tools(system, msgs, SALON_TOOLS, required=force_tools)
        tcs = resp.get("tool_calls")
        if tcs:
            results = {}
            for tc in tcs:
                results[tc["id"]] = execute_tool(tc["name"], tc["args"])
                # Capture booking details from successful tool call
                if tc["name"] == "salon_book_appointment":
                    r = json.loads(results[tc["id"]])
                    if r.get("potrjeno"):
                        state["booking_confirmed"] = True
                        state["booking_date"] = tc["args"].get("datum", "")
                        state["booking_time"] = tc["args"].get("ura", "")

            # DETERMINISTIC: If we're in availability/booking, have contact, haven't booked yet,
            # and the user already specified a service + date + time — auto-book.
            if stage in ("availability", "booking") and not state.get("booking_confirmed"):
                contact_ok = json.loads(execute_tool("salon_check_contact", {}))
                if contact_ok.get("ok"):
                    # Try to extract service + date + time from LLM tool calls or recent messages
                    extracted = _extract_booking_intent(latest, recent, tcs)
                    if extracted:
                        auto_args = {"storitev_id": extracted["service_id"], "datum": extracted["date"], "ura": extracted["time"], "ime_stranke": extracted.get("name", "Stranka")}
                        auto_result = execute_tool("salon_book_appointment", auto_args)
                        auto_tc_id = "auto_booking"
                        results[auto_tc_id] = auto_result
                        msgs.append({"role": "assistant", "content": None, "tool_calls": [
                            {"id": auto_tc_id, "type": "function", "function": {"name": "salon_book_appointment", "arguments": json.dumps(auto_args)}}
                        ]})
                        msgs.append({"role": "tool", "tool_call_id": auto_tc_id, "content": auto_result})
                        r = json.loads(auto_result)
                        if r.get("potrjeno"):
                            state["booking_confirmed"] = True
                            state["booking_date"] = extracted["date"]
                            state["booking_time"] = extracted["time"]

            for tc in tcs:
                msgs.append({"role": "assistant", "content": None, "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                ]})
                msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": results[tc["id"]]})
            reply = llm.call_json_response(system, msgs)
        else:
            reply = resp.get("text", "")

    if not reply:
        reply = llm.call_text(system, latest_json)

    # Unwrap JSON if the LLM returned {"rep":"..."} instead of plain text
    reply = _unwrap_reply(reply)

    if not reply:
        reply = "Dober dan! Kako vam lahko pomagam? 💆‍♀️"

    # Update state flags
    if stage == "greeting":
        state["hours_mentioned"] = True
        state["services_presented"] = True

    interpretation = TurnInterpretation(
        visitor_type="new_visitor",
        preferred_language="sl",
        used_llm=bool(reply),
        model_name=llm.model_name,
    )
    decision = TurnDecision(
        reply=reply,
        recommended_next_action="continue_conversation",
        funnel_stage=stage,
        qualification_band="warm",
        qualification_score=55,
        confidence_overall=0.5,
        used_llm=bool(reply),
        model_name=llm.model_name,
    )
    state["interpretation"] = interpretation
    state["decision"] = decision
    return state


def _extract_booking_intent(latest: str, recent: list, tool_calls: list) -> dict | None:
    """Extract booking details (service_id, date, time) from conversation context.
    Checks LLM tool calls first, then scans message text for service keywords and time patterns."""
    import re

    # 1. Check tool calls for salon_check_availability/salon_book_appointment args
    for tc in (tool_calls or []):
        if tc["name"] in ("salon_check_availability", "salon_book_appointment"):
            args = tc["args"]
            svc = args.get("storitev_id", "")
            dt = args.get("datum", "")
            tm = args.get("ura", "")
            if svc and dt and tm:
                return {"service_id": svc, "date": dt, "time": tm, "name": args.get("ime_stranke", "Stranka")}

    # 2. Scan recent messages for explicit booking details
    all_text = latest
    for m in (recent or [])[-3:]:
        all_text += " . " + (m.get("text", "") or "")
    all_lower = all_text.lower()

    # Service detection
    service_id = None
    if "nega obraza" in all_lower or "nego obraza" in all_lower or "nege obraza" in all_lower:
        service_id = "nega-obraza"
    elif "maska obraza" in all_lower or "masko obraza" in all_lower:
        service_id = "maska-obraza"
    elif "čiščenje" in all_lower or "ciscenje" in all_lower or "čiščenja" in all_lower:
        service_id = "ciscenje-obraza"

    if not service_id:
        return None

    # Date detection: "jutri", "danes", "pojutrišnjem", explicit YYYY-MM-DD
    date = None
    from datetime import datetime, timedelta
    today = datetime.now()
    if "jutri" in all_lower:
        date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "danes" in all_lower:
        date = today.strftime("%Y-%m-%d")
    elif "pojutrišnjem" in all_lower or "pojutrisnjem" in all_lower:
        date = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    else:
        m = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', all_text)
        if m:
            date = m.group(1)

    if not date:
        # Check if LLM already specified a date in tool args
        if tool_calls:
            for tc in tool_calls:
                d = (tc.get("args") or {}).get("datum", "")
                if d:
                    date = d
                    break

    if not date:
        return None

    # Time detection: "ob 11:00", "9:30", "10h", "ob 10ih"
    time = None
    tm = re.search(r'\b(\d{1,2}):(\d{2})\b', all_text)
    if tm:
        time = f"{int(tm.group(1)):02d}:{tm.group(2)}"
    else:
        tm2 = re.search(r'\b(\d{1,2})\.(\d{2})\b', all_text)
        if tm2:
            time = f"{int(tm2.group(1)):02d}:{tm2.group(2)}"
    
    if not time:
        # Check tool call args
        if tool_calls:
            for tc in tool_calls:
                t = (tc.get("args") or {}).get("ura", "")
                if t:
                    time = t
                    break

    if not time:
        return None

    # Name extraction: "ime mi je X", "sem X", "moje ime je X", "kličem se X"
    name = "Stranka"
    name_patterns = [
        r'(?:ime\s+(?:mi\s+)?je\s+|moje\s+ime\s+je\s+|kličem\s+se\s+|pišem\s+se\s+|sem\s+)([A-ZČŠŽ][a-zčšž]+(?:\s+[A-ZČŠŽ][a-zčšž]+)?)',
        r'(?:jaz\s+sem\s+)([A-ZČŠŽ][a-zčšž]+(?:\s+[A-ZČŠŽ][a-zčšž]+)?)',
    ]
    for pat in name_patterns:
        m = re.search(pat, all_text)
        if m:
            name = m.group(1).strip()
            break

    return {"service_id": service_id, "date": date, "time": time, "name": name}


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


# ── Entry point ──

def _unwrap_reply(text: str) -> str:
    """If LLM returned JSON {"rep":"..."}, extract just the reply text."""
    if not text:
        return ""
    text = text.strip()
    if text.startswith("{") and '"rep"' in text:
        try:
            data = json.loads(text)
            return data.get("rep", text)
        except (json.JSONDecodeError, TypeError):
            pass
    return text


def run_qualification_graph(
    *,
    llm: LLMService,
    qualifier: Any,
    latest_message: str,
    recent_messages: List[Dict[str, str]],
    profile_before: Dict[str, Any],
    spatial_context: Optional[Dict[str, Any]] = None,
) -> QualificationGraphState:
    # Carry forward conversation state from profile
    state: QualificationGraphState = {
        "qualifier": qualifier,
        "latest_message": latest_message,
        "recent_messages": recent_messages,
        "profile_before": profile_before,
        "spatial_context": spatial_context,
        "conversation_stage": profile_before.get("conversation_stage") or "",
        "hours_mentioned": profile_before.get("hours_mentioned", False),
        "services_presented": profile_before.get("services_presented", False),
        "service_interest": profile_before.get("service_interest", ""),
        "booking_date": profile_before.get("booking_date", ""),
        "booking_time": profile_before.get("booking_time", ""),
        "booking_confirmed": False,
    }

    if StateGraph is None:
        state = _load_runtime_context(state)
        state = _classify_intent(state)
        stage = state.get("conversation_stage", "greeting")
        return _reply_for_stage(state, stage)

    graph = StateGraph(QualificationGraphState)

    # Nodes
    graph.add_node("load_runtime_context", _load_runtime_context)
    graph.add_node("retrieve_knowledge", _retrieve_knowledge)
    graph.add_node("classify_intent", _classify_intent)
    graph.add_node("greeting", _greeting_node)
    graph.add_node("discovery", _discovery_node)
    graph.add_node("availability", _availability_node)
    graph.add_node("booking", _booking_node)
    graph.add_node("handoff", _handoff_node)
    graph.add_node("idle", _idle_node)

    # Edges
    graph.set_entry_point("load_runtime_context")
    graph.add_edge("load_runtime_context", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "classify_intent")

    # Conditional routing from classify to stage-specific node
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_stage,
        {
            "greeting": "greeting",
            "discovery": "discovery",
            "availability": "availability",
            "booking": "booking",
            "handoff": "handoff",
            "idle": "idle",
        },
    )

    # All stage nodes go to END
    for stage_node in ("greeting", "discovery", "availability", "booking", "handoff", "idle"):
        graph.add_edge(stage_node, END)

    return graph.compile().invoke(state)
