from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.qualification.runtime_context import build_runtime_context, retrieve_knowledge
from app.qualification.state import (
    QualificationGraphState,
    TurnDecision,
)
from app.services.llm_service import LLMService
from app.qualification.tools import ACE_TOOLS, execute_tool


# ═══════════════════════════════════════════════════════════
#  Agent — ONE LLM call with full context + all tools
# ═══════════════════════════════════════════════════════════

def _build_agent_prompt(state: QualificationGraphState) -> str:
    """Build a single rich prompt with everything the LLM needs."""
    latest = state.get("latest_message", "")
    recent = state.get("recent_messages", []) or []
    last_booking_id = state.get("last_booking_id")

    # Business hours
    biz = json.loads(execute_tool("ace_get_context", {}))

    # Contact status
    contact = json.loads(execute_tool("ace_check_contact", {}))

    # Conversation history
    history = "\n".join(
        f"  {m.get('role','?')}: {m.get('text','')[:200]}"
        for m in (recent or [])[-8:]
    )

    prompt = f"""Ti si AI Svetovalec za ACE — podjetje, ki razvija AI recepcijske rešitve za avtomatizacijo sprejema strank.
ACE ponuja: AI Reception (avtomatska kvalifikacija, booking, handoff), Analytics (dashboard, konverzijske metrike), Integrations (LiveKit, koledar, plačila), AI Lead Scoring (samodejno ocenjevanje leadov).
Si prijazen, direkten, posloven. Govoriš naravno slovenščino.
STROGO UPORABLJAJ VIKANJE (vi, vas, vaš, sporočite, izberite).
NIKOLI ne uporabljaj tikanja (ti, te, tvoj, sporoči, izberi).

TRENUTNO STANJE:
  Status: {biz.get('status','')}
  Delovni čas: {biz.get('delovni_cas','')}
  Danes: {biz.get('danes','')}
  Naslednji delovni dan: {biz.get('naslednji_delovni_dan','')}

KONTAKT STRANKE:
  {'Stranka JE podala kontakt (telefon ali email).' if contact.get('ok') else 'Stranka ŠE NI podala kontakta. Pred klicem ga MORAŠ pridobiti (telefon ali email).'}

{"ZADNJI KLIC ID: " + str(last_booking_id) if last_booking_id else "Ni še dogovorjenega klica v tem pogovoru."}

ZGODOVINA POGOVORA:
{history if history else '(prazen — prvi stik)'}

STRANKA PRAVI: {json.dumps(latest, ensure_ascii=False)}

TVOJA NALOGA:
1. Če stranka pozdravlja — toplo pozdravi, na kratko predstavi ACE (1 stavek), vprašaj kako lahko pomagaš.
2. Če stranka sprašuje o storitvah — odgovori direktno, opiši kaj ACE ponuja.
3. Če stranka opisuje svoje potrebe — postavi vprašanja za kvalifikacijo: koliko strank, kakšen sistem zdaj, kakšne so njihove potrebe.
4. Če je stranka dovolj kvalificirana (je opisala potrebe) in IMA KONTAKT — ponudi klic z ekipo. Pokliči ace_schedule_call. Datum naj bo naslednji delovni dan.
5. Če ZADNJI KLIC ID že obstaja, NE kliči ace_schedule_call ponovno.
6. Če stranka želi govoriti z osebo — pokliči ace_request_team.
7. Če je podjetje zaprto — povej da bomo odgovorili naslednji delovni dan, prosi za kontakt če ga še ni.
8. Če je stranka samo potrdila, se strinja ("ok", "super", "hvala") — NE kliči nobenega orodja. Samo kratko potrdi.

Bodi kratek (1-3 stavke), naraven, vikanje. Ne izmišljuj si cen ali paketov."""

    return prompt


def _run_tools_phase(state: QualificationGraphState, llm: LLMService):
    """Run LLM with tools, execute any tool calls, return (system, msgs, had_tools, blocked_booking)."""
    latest = state.get("latest_message", "")
    system = _build_agent_prompt(state)
    msgs = [{"role": "user", "content": json.dumps(latest, ensure_ascii=False)}]

    contact = json.loads(execute_tool("ace_check_contact", {}))
    has_contact = contact.get("ok")

    tools = ACE_TOOLS
    resp = llm.call_with_tools(system, msgs, tools, required=False)
    tcs = resp.get("tool_calls")
    all_tcs = []

    blocked_booking = False
    if tcs:
        if not has_contact:
            booking_tcs = [tc for tc in tcs if tc["name"] == "ace_schedule_call"]
            if booking_tcs:
                blocked_booking = True
                tcs = [tc for tc in tcs if tc["name"] != "ace_schedule_call"]

    if tcs:
        for tc in tcs:
            result = execute_tool(tc["name"], tc["args"])
            all_tcs.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
            if tc["name"] == "ace_schedule_call":
                r = json.loads(result)
                if r.get("potrjeno"):
                    state["booking_confirmed"] = True
                    state["booking_date"] = tc["args"].get("datum", "")
                    state["booking_time"] = tc["args"].get("ura", "")
                    state["last_booking_id"] = r.get("id")

        for tc in all_tcs:
            msgs.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
            ]})
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": tc["result"]})

    if blocked_booking:
        msgs.append({"role": "user", "content": "POZOR: Stranka še nima kontakta. Ne smeš rezervirati klica brez kontakta. Vljudno prosi za telefonsko številko ali email."})

    # Guard: if no booking tool was called but user mentions time/date, force a second tool pass
    booking_tool_names = {"ace_schedule_call"}
    had_booking_tool = any(tc["name"] in booking_tool_names for tc in all_tcs)
    already_booked = bool(state.get("last_booking_id"))
    if not had_booking_tool and has_contact and not already_booked:
        import re as _re
        has_date = bool(_re.search(r'\d{1,2}\.\d{1,2}\.|\d{4}-\d{2}-\d{2}|jutri|danes|pojutrišnjem|ponedeljek|torek|sredo|sreda|četrtek|petek|soboto|nedeljo|naslednji teden|ta teden', latest.lower()))
        has_time = bool(_re.search(r'ob\s+\d|\d{1,2}:\d{2}|\d{1,2}\.00|opoldne|dopoldne|popoldne|zjutraj|dopoldan|popoldan|enih|dveh|treh|štirih|petih|šestih|sedmih|osmih|devetih|desetih|enajstih|dvanajstih', latest.lower()))
        if has_date or has_time:
            msgs.append({"role": "user", "content": "MORAŠ poklicati orodje (ace_schedule_call). Ne smeš samo reči da boš uredil — dejansko pokliči orodje."})
            resp2 = llm.call_with_tools(system, msgs, [t for t in tools if t["function"]["name"] != "ace_check_contact"], required=True)
            tcs2 = resp2.get("tool_calls")
            if tcs2:
                second_results = []
                for tc in tcs2:
                    if not has_contact and tc["name"] == "ace_schedule_call":
                        continue
                    result = execute_tool(tc["name"], tc["args"])
                    second_results.append((tc, result))
                    all_tcs.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
                    if tc["name"] == "ace_schedule_call":
                        r = json.loads(result)
                        if r.get("potrjeno"):
                            state["booking_confirmed"] = True
                            state["booking_date"] = tc["args"].get("datum", "")
                            state["booking_time"] = tc["args"].get("ura", "")
                            state["last_booking_id"] = r.get("id")
                for tc, result in second_results:
                    msgs.append({"role": "assistant", "content": None, "tool_calls": [
                        {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                    ]})
                    msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    return system, msgs, bool(all_tcs), blocked_booking


def _agent_node(state: QualificationGraphState) -> QualificationGraphState:
    """ONE LLM call with full context + all tools. No keyword gating — trust the prompt."""
    llm = LLMService()
    latest = state.get("latest_message", "")

    system, msgs, had_tools, blocked_booking = _run_tools_phase(state, llm)

    # Generate final response (non-streaming)
    reply = llm.call_json_response(system, msgs)
    reply = _unwrap_reply(reply)
    if not reply:
        fallback_user = json.dumps(latest, ensure_ascii=False)
        reply = llm.call_text(system, fallback_user)
    if not reply:
        reply = "Pozdravljeni! Smo ACE. Kako vam lahko pomagamo?"

    if not state.get("hours_mentioned"):
        state["hours_mentioned"] = True
    state["services_presented"] = True
    state["conversation_stage"] = "idle"

    state["decision"] = TurnDecision(
        reply=reply,
        recommended_next_action="continue_conversation",
        funnel_stage="agent",
        qualification_band="warm",
        qualification_score=55,
        confidence_overall=0.5,
        used_llm=True,
        model_name=llm.model_name,
    )
    state["tool_messages"] = msgs
    return state


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
#  Entry point
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

    state = _load_runtime_context(state)
    state = _retrieve_knowledge(state)
    return _agent_node(state)


def run_qualification_graph_stream(
    *,
    llm: LLMService,
    qualifier: Any,
    latest_message: str,
    recent_messages: List[Dict[str, str]],
    profile_before: Dict[str, Any],
    spatial_context: Optional[Dict[str, Any]] = None,
):
    """Streaming variant — yields tokens during final reply."""
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
    state = _load_runtime_context(state)
    state = _retrieve_knowledge(state)

    # Run tool phase (blocking)
    system, msgs, tcs_executed, blocked_booking = _run_tools_phase(state, llm)
    
    latest = state.get("latest_message", "")
    reply = ""
    
    if tcs_executed:
        # Tools were called — use non-streaming final reply
        reply = llm.call_json_response(system, msgs)
        reply = _unwrap_reply(reply)
        if not reply:
            summary_parts = []
            for m in msgs:
                if m.get("role") == "tool":
                    try:
                        r = json.loads(m["content"])
                        summary_parts.append(r.get("sporocilo", m["content"][:300]))
                    except Exception:
                        summary_parts.append(m["content"][:300])
            fallback_user = ("Rezultati orodij: " + " | ".join(summary_parts)) if summary_parts else json.dumps(latest, ensure_ascii=False)
            reply = llm.call_text(system, fallback_user) or reply
        if not reply:
            reply = "Pozdravljeni! Smo ACE. Kako vam lahko pomagamo?"
        for ch in reply:
            yield ch
    else:
        # No tools — stream directly from LLM
        stream_msgs = [{"role": "user", "content": json.dumps(latest, ensure_ascii=False)}]
        for token in llm.stream_reply(system, stream_msgs):
            if token:
                reply += token
                yield token
        reply = reply.strip()
        if not reply:
            reply = "Pozdravljeni! Smo ACE. Kako vam lahko pomagamo?"
            yield reply

    # Finalize state
    if not state.get("hours_mentioned"):
        state["hours_mentioned"] = True
    state["services_presented"] = True
    state["conversation_stage"] = "idle"
    state["decision"] = TurnDecision(
        reply=reply,
        recommended_next_action="continue_conversation",
        funnel_stage="agent",
        qualification_band="warm",
        qualification_score=55,
        confidence_overall=0.5,
        used_llm=True,
        model_name=llm.model_name,
    )
    state["tool_messages"] = msgs


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
