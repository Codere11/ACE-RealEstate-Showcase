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


# ═══════════════════════════════════════════════════════════
#  LangGraph nodes — each does ONE thing
# ═══════════════════════════════════════════════════════════

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


def _classify_intent(state: QualificationGraphState) -> QualificationGraphState:
    """Determine what the customer wants RIGHT NOW — output: conversation_stage."""
    latest = state.get("latest_message", "").strip()
    recent = state.get("recent_messages", []) or []
    existing_stage = state.get("conversation_stage", "")

    lowered = latest.lower()
    greeting_words = {"dober dan", "zdravo", "živjo", "pozdravljeni", "pozdravljena",
                       "dober večer", "dober dan!", "živjo!", "hej", "oj", "hi", "hello"}
    is_just_greeting = lowered in greeting_words or (len(lowered.split()) <= 2 and any(
        g in lowered for g in ["dober", "zdravo", "živjo", "pozdrav", "hej", "oj", "hi"]))

    if existing_stage and existing_stage != "greeting" and is_just_greeting:
        state["conversation_stage"] = "idle"
        return state

    llm = LLMService()
    if llm.is_available() and latest:
        prompt = build_classify_prompt(latest, recent)
        result = llm.call_json(prompt, latest)
        stage: ConversationStage = result.get("stage", "greeting") if isinstance(result, dict) else "greeting"
    else:
        stage = "greeting"

    if existing_stage and stage == "greeting" and existing_stage != "greeting":
        stage = existing_stage
    if existing_stage in ("availability", "booking") and stage in ("greeting", "idle", "discovery"):
        stage = existing_stage
    elif not existing_stage and is_just_greeting:
        stage = "greeting"
    elif existing_stage == "greeting" and is_just_greeting:
        stage = "idle"

    state["conversation_stage"] = stage
    return state


def _call_tools(state: QualificationGraphState) -> QualificationGraphState:
    """Build prompt, call LLM with tools, execute any tool calls. Stores results in state."""
    llm = LLMService()
    latest = state.get("latest_message", "")
    recent = (state.get("recent_messages", []) or [])[-6:]
    stage = state.get("conversation_stage", "greeting")
    hours_mentioned = state.get("hours_mentioned", False)
    services_presented = state.get("services_presented", False)

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

    # Deterministic contact check for booking stages
    contact_missing = False
    if stage in ("availability", "booking"):
        contact = json.loads(execute_tool("salon_check_contact", {}))
        if not contact.get("ok"):
            system += "\n\nPOZOR: Stranka NIMA kontaktnih podatkov. Vljudno prosi za telefonsko ali email PREDEN rezerviraš. NE kaži terminov dokler ne dobiš kontakta. Ne kliči salon_book_appointment dokler nimaš kontakta."
            contact_missing = True

    needs_tools = stage in ("greeting", "discovery", "availability", "booking", "handoff", "addon", "cancel")
    force_tools = stage in ("availability", "booking", "addon", "cancel")
    msgs = [{"role": "user", "content": latest_json}]
    tool_results = {}
    tool_calls_list = []

    if needs_tools and llm.is_available():
        resp = llm.call_with_tools(system, msgs, SALON_TOOLS, required=force_tools)
        tcs = resp.get("tool_calls")
        if tcs:
            for tc in tcs:
                result = execute_tool(tc["name"], tc["args"])
                tool_results[tc["id"]] = result
                tool_calls_list.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
                # If LLM actually called salon_book_appointment and it succeeded, mark as confirmed
                if tc["name"] == "salon_book_appointment":
                    r = json.loads(result)
                    if r.get("potrjeno"):
                        state["booking_confirmed"] = True
                        state["booking_date"] = tc["args"].get("datum", "")
                        state["booking_time"] = tc["args"].get("ura", "")
            # Build message history for reply generation
            for tc in tool_calls_list:
                msgs.append({"role": "assistant", "content": None, "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                ]})
                msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": tc["result"]})

        # SECOND PASS: force LLM to call booking tools (book_appointment or check_availability)
        booking_tools = [t for t in SALON_TOOLS if t["function"]["name"] in ("salon_check_availability", "salon_book_appointment")]
        if stage in ("availability", "booking") and not contact_missing and llm.is_available():
            resp2 = llm.call_with_tools(system, msgs, booking_tools, required=True)
            tcs2 = resp2.get("tool_calls")
            if tcs2:
                for tc in tcs2:
                    result = execute_tool(tc["name"], tc["args"])
                    tool_results[tc["id"]] = result
                    tool_calls_list.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
                    if tc["name"] == "salon_book_appointment":
                        r = json.loads(result)
                        if r.get("potrjeno"):
                            state["booking_confirmed"] = True
                            state["booking_date"] = tc["args"].get("datum", "")
                            state["booking_time"] = tc["args"].get("ura", "")
                            state["last_booking_id"] = r.get("id")
                for tc in tcs2:
                    msgs.append({"role": "assistant", "content": None, "tool_calls": [
                        {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                    ]})
                    msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_results[tc["id"]]})

        # ADDON SECOND PASS: if addon stage, force salon_add_addon after list_addons
        if stage == "addon" and llm.is_available():
            has_added = any(tc["name"] == "salon_add_addon" for tc in tool_calls_list)
            if not has_added:
                addon_only = [t for t in SALON_TOOLS if t["function"]["name"] == "salon_add_addon"]
                resp3 = llm.call_with_tools(system, msgs, addon_only, required=True)
                tcs3 = resp3.get("tool_calls")
                if tcs3:
                    for tc in tcs3:
                        result = execute_tool(tc["name"], tc["args"])
                        tool_results[tc["id"]] = result
                        tool_calls_list.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
                    for tc in tcs3:
                        msgs.append({"role": "assistant", "content": None, "tool_calls": [
                            {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                        ]})
                        msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_results[tc["id"]]})

    state["tool_results"] = tool_results
    state["tool_calls"] = tool_calls_list
    state["tool_messages"] = msgs

    # If any addon tool was called, append validation to system prompt
    for tc in tool_calls_list:
        if tc["name"] == "salon_add_addon":
            r = json.loads(tc["result"]) if isinstance(tc["result"], str) else tc["result"]
            if r.get("napaka"):
                system += f"\n\nPOZOR: Dopolnitve {tc['args'].get('addon_id','')} ni bilo mogoče dodati: {r['napaka']}. V odgovoru NE trdi da je bila dodana. Pojasni da ni na voljo in naštej kaj JE na voljo (pokliči salon_list_addons)."
            elif r.get("dodano"):
                system += f"\n\nDopolnitev {r.get('dopolnitev','')} je bila uspešno dodana. Omeni jo v odgovoru s ceno."
    # Always: if booking stage and contact exists, warn LLM not to invent add-ons not in the real list
    if stage in ("availability", "booking") and not contact_missing:
        system += "\n\nPOZOR: Če stranka omenja dopolnitve ki jih ni v seznamu salon_list_addons — NE vključi jih v odgovor kot da so dodane. Pojasni da niso na voljo in naštej alternative."
    state["system_prompt"] = system
    state["contact_missing"] = contact_missing
    state["latest_json"] = latest_json
    # Detect: staff requested but salon closed
    state["salon_closed_request"] = False
    for tc in tool_calls_list:
        if tc["name"] == "salon_request_staff":
            r = json.loads(tc["result"])
            if not r.get("uspesno", True):
                state["salon_closed_request"] = True
                state["contact_missing"] = True  # force contact capture
    return state


def _check_booking(state: QualificationGraphState) -> str:
    """Conditional edge: where to route after call_tools? Returns 'auto_book', 'capture_contact', or 'generate_reply'."""
    # Closed-hours staff request with no contact → capture contact
    if state.get("salon_closed_request") and state.get("contact_missing"):
        return "capture_contact"
    stage = state.get("conversation_stage", "")
    if stage not in ("availability", "booking"):
        return "generate_reply"
    if state.get("booking_confirmed"):
        return "generate_reply"
    if state.get("contact_missing"):
        return "generate_reply"

    latest = state.get("latest_message", "")
    recent = state.get("recent_messages", []) or []
    tcs = state.get("tool_calls", []) or []
    extracted = _extract_booking_intent(latest, recent, tcs)
    if extracted:
        state["booking_extracted"] = extracted
        return "auto_book"
    return "generate_reply"


def _capture_contact(state: QualificationGraphState) -> QualificationGraphState:
    """LangGraph node: salon closed, staff requested, no contact. LLM asks for email/phone."""
    llm = LLMService()
    latest = state.get("latest_message", "")
    salon_state = json.loads(execute_tool("salon_get_context", {}))
    naslednji_dan = salon_state.get("naslednji_delovni_dan", "")
    delovni_cas = salon_state.get("delovni_cas", "pon–pet 9:00–18:00")

    system = (
        f"Ti si AI Receptor za kozmetični salon. Govoriš naravno slovenščino. "
        f"STROGO uporabljaš vikanje (vi, vas, vaš, sporočite). NIKOLI tikanja (ti, te, tvoj, sporoči).\n\n"
        f"Salon je trenutno ZAPRT. Delovni čas: {delovni_cas}. Naslednji delovni dan: {naslednji_dan}.\n"
        f"Stranka je želela govoriti z osebjem, vendar je salon zaprt.\n"
        f"Vljudno povej da je salon zaprt, povej kdaj bo spet odprt, "
        f"in prosi stranko naj pusti email ali telefonsko številko, da jo kontaktiramo.\n"
        f"Uporabljaj vikanje: 'vas', 'vaš', 'vaša', 'sporočite' — nikoli 'te', 'tvoj', 'sporoči'.\n"
        f"Bodi topel, profesionalen. 2-3 stavke."
    )

    msgs = state.get("tool_messages", []) or []
    reply = llm.call_json_response(system, msgs)
    reply = _unwrap_reply(reply)
    if not reply:
        reply = llm.call_text(system, json.dumps(latest, ensure_ascii=False))
    if not reply:
        reply = f"Salon je trenutno zaprt ({delovni_cas}). Lahko pustite vaš email ali telefonsko številko in vas kontaktiramo naslednji delovni dan ({naslednji_dan})."

    state["auto_book_reply"] = reply
    return state


def _suggest_addons(state: QualificationGraphState) -> QualificationGraphState:
    """LangGraph node: after booking confirmed, LLM softly suggests ONE add-on from the real list."""
    if not state.get("booking_confirmed"):
        return state
    if state.get("auto_book_reply"):
        return state

    extracted = state.get("booking_extracted", {})
    service_id = extracted.get("service_id", "") if extracted else ""
    if not service_id:
        return state

    llm = LLMService()
    addons_json = execute_tool("salon_list_addons", {"storitev_id": service_id})
    addons = json.loads(addons_json).get("dopolnitve", [])
    if not addons:
        return state

    addon_list = ", ".join(f"{a['name']} (+{a['price_eur']}€)" for a in addons)

    system = (
        f"Ti si AI Receptor za kozmetični salon. Govoriš naravno slovenščino. "
        f"STROGO uporabljaš vikanje (vi, vas, vaš).\n\n"
        f"Stranka je pravkar rezervirala: {service_id}. "
        f"Edine dopolnitve, ki so na voljo: {addon_list}. "
        f"NE izmišljaj si drugih dopolnitev — uporabi SAMO te.\n\n"
        f"Če se ti zdi primerno, predlagaj ENO od teh dopolnitev. "
        f"Bodi nežen — en stavek, npr. 'Bi želeli dodati še X za Y€?' "
        f"Če ni primerno, vrni prazen odgovor. NE vsiljuj.\n\n"
        f"Vrni SAMO predlog ali prazen niz. 0-1 stavek."
    )

    reply = llm.call_text(system, json.dumps(state.get("latest_message", ""), ensure_ascii=False))
    reply = (reply or "").strip()
    if reply and len(reply) > 3:
        state["addon_suggestion"] = reply
    return state


def _auto_book(state: QualificationGraphState) -> QualificationGraphState:
    """Deterministic booking: call salon_book_appointment with extracted intent. Bypasses LLM for reply."""
    extracted = state.get("booking_extracted", {})
    if not extracted:
        state["decision"] = TurnDecision(reply="", recommended_next_action="continue_conversation",
                                          funnel_stage=state.get("conversation_stage", ""),
                                          qualification_band="warm", qualification_score=55,
                                          confidence_overall=0.5, used_llm=False, model_name="")
        return state

    auto_args = {
        "storitev_id": extracted["service_id"],
        "datum": extracted["date"],
        "ura": extracted["time"],
        "ime_stranke": extracted.get("name", "Stranka"),
        "dodatki": extracted.get("dodatki", []),
    }
    result_json = execute_tool("salon_book_appointment", auto_args)
    result = json.loads(result_json)

    if result.get("potrjeno"):
        state["booking_confirmed"] = True
        state["booking_date"] = extracted["date"]
        state["booking_time"] = extracted["time"]
        state["last_booking_id"] = result.get("id")
        reply = result.get("sporocilo", "")
    else:
        msgs = state.get("tool_messages", []) or []
        msgs.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "auto_booking", "type": "function", "function": {"name": "salon_book_appointment", "arguments": json.dumps(auto_args)}}
        ]})
        msgs.append({"role": "tool", "tool_call_id": "auto_booking", "content": result_json})
        state["tool_messages"] = msgs
        reply = ""

    state["auto_book_reply"] = reply
    return state


def _generate_reply(state: QualificationGraphState) -> QualificationGraphState:
    """Generate final text reply from tool results using LLM, or use already-set reply from auto_book."""
    llm = LLMService()
    reply = state.get("auto_book_reply", "") or ""
    msgs = state.get("tool_messages", []) or []
    # If add-on tools were called, let LLM generate a proper response including add-on info
    has_addon_results = any("salon_list_addons" in str(m) or "salon_add_addon" in str(m) for m in msgs)
    if reply and not has_addon_results:
        pass
    else:
        system = state.get("system_prompt", "")
        latest_json = state.get("latest_json", "")
        if msgs:
            reply = llm.call_json_response(system, msgs) or ""
        if not reply:
            reply = llm.call_text(system, latest_json) or ""
        reply = _unwrap_reply(reply)

    if not reply:
        reply = "Dober dan! Kako vam lahko pomagam? 💆‍♀️"

    # Append add-on suggestion if available
    suggestion = state.get("addon_suggestion", "")
    if suggestion and suggestion not in reply:
        reply = reply.rstrip() + "\n\n" + suggestion

    # Update state flags
    stage = state.get("conversation_stage", "")
    if stage == "greeting":
        state["hours_mentioned"] = True
        state["services_presented"] = True

    interpretation = TurnInterpretation(
        visitor_type="new_visitor",
        preferred_language="sl",
        used_llm=bool(reply),
        model_name=llm.model_name,
    )
    state["interpretation"] = interpretation
    state["decision"] = TurnDecision(
        reply=reply,
        recommended_next_action="continue_conversation",
        funnel_stage=stage,
        qualification_band="warm",
        qualification_score=55,
        confidence_overall=0.5,
        used_llm=bool(reply),
        model_name=llm.model_name,
    )
    return state


# ═══════════════════════════════════════════════════════════
#  Booking intent extraction (pure function, no side effects)
# ═══════════════════════════════════════════════════════════

def _extract_booking_intent(latest: str, recent: list, tool_calls: list) -> dict | None:
    """Extract booking details from LLM tool calls — the LLM already parsed
    dates, times, and service IDs into structured arguments."""
    for tc in (tool_calls or []):
        if tc.get("name") in ("salon_check_availability", "salon_book_appointment"):
            args = tc.get("args", {})
            svc = args.get("storitev_id", "")
            dt = args.get("datum", "")
            tm = args.get("ura", "")
            name = args.get("ime_stranke", "Stranka")
            if svc and dt and tm:
                # Pass any additional add-on IDs the LLM included
                addon_ids = args.get("dodatki", []) or []
                return {"service_id": svc, "date": dt, "time": tm, "name": name, "dodatki": addon_ids}
    return None


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def _unwrap_reply(text: str) -> str:
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


# ═══════════════════════════════════════════════════════════
#  Entry point — build and run the graph
# ═══════════════════════════════════════════════════════════

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
        "conversation_stage": profile_before.get("conversation_stage") or "",
        "hours_mentioned": profile_before.get("hours_mentioned", False),
        "services_presented": profile_before.get("services_presented", False),
        "service_interest": profile_before.get("service_interest", ""),
        "booking_date": profile_before.get("booking_date", ""),
        "booking_time": profile_before.get("booking_time", ""),
        "booking_confirmed": False,
        "last_booking_id": profile_before.get("last_booking_id"),
    }

    # Use sequential pipeline — battle-tested, no serialization issues
    state = _load_runtime_context(state)
    state = _retrieve_knowledge(state)
    state = _classify_intent(state)
    state = _call_tools(state)
    route = _check_booking(state)
    if route == "auto_book":
        state = _auto_book(state)
    elif route == "capture_contact":
        state = _capture_contact(state)
    state = _suggest_addons(state)
    state = _generate_reply(state)
    return state
