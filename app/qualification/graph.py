from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.qualification.runtime_context import build_runtime_context, retrieve_knowledge
from app.qualification.state import (
    QualificationGraphState,
    TurnDecision,
)
from app.services.llm_service import LLMService
from app.qualification.tools import SALON_TOOLS, execute_tool
from app.qualification.tools import ADDONS


# ═══════════════════════════════════════════════════════════
#  Agent — ONE LLM call with full context + all tools
# ═══════════════════════════════════════════════════════════

def _build_agent_prompt(state: QualificationGraphState) -> str:
    """Build a single rich prompt with everything the LLM needs."""
    latest = state.get("latest_message", "")
    recent = state.get("recent_messages", []) or []
    last_booking_id = state.get("last_booking_id")

    # Salon state
    salon = json.loads(execute_tool("salon_get_context", {}))

    # Service + add-on info
    service_info = []
    for s in [
        {"id": "nega-obraza", "name": "Nega obraza", "dur": 45, "price": 45},
        {"id": "maska-obraza", "name": "Maska obraza", "dur": 30, "price": 30},
        {"id": "ciscenje-obraza", "name": "Čiščenje obraza", "dur": 60, "price": 60},
    ]:
        addons = ADDONS.get(s["id"], [])
        addon_str = ", ".join(f"{a['name']} (+{a['price_eur']}€, id={a['id']})" for a in addons)
        service_info.append(f"  {s['id']}: {s['name']} ({s['dur']}min, {s['price']}€) — dopolnitve: {addon_str}")

    # Conversation history
    history = "\n".join(
        f"  {m.get('role','?')}: {m.get('text','')[:200]}"
        for m in (recent or [])[-8:]
    )

    # Contact status
    contact = json.loads(execute_tool("salon_check_contact", {}))

    # Use qualifier name from config, fall back to default
    qualifier = state.get("qualifier")
    salon_name = getattr(qualifier, "name", None) or "Lepota & Sprostitev"

    prompt = f"""Ti si AI Receptor za kozmetični salon {salon_name}.
Si prijazen, topel, profesionalen — kot izkušen receptor.
Govoriš naravno slovenščino, kratko in jedrnato.
STROGO UPORABLJAJ VIKANJE (vi, vas, vaš, sporočite, izberite).
NIKOLI ne uporabljaj tikanja (ti, te, tvoj, sporoči, izberi).

TRENUTNO STANJE SALONA:
  Status: {salon.get('status','')}
  Delovni čas: {salon.get('delovni_cas','')}
  Danes: {salon.get('danes','')}
  Naslednji delovni dan: {salon.get('naslednji_delovni_dan','')}

STORITVE IN DOPOLNITVE:
{chr(10).join(service_info)}

KONTAKT STRANKE:
  {'Stranka JE podala kontakt (telefon ali email).' if contact.get('ok') else 'Stranka ŠE NI podala kontakta. Pred rezervacijo ga MORAŠ pridobiti.'}

{"ZADNJA REZERVACIJA ID: " + str(last_booking_id) if last_booking_id else "Ni še rezervacije v tem pogovoru."}

ZGODOVINA POGOVORA:
{history if history else '(prazen — prvi stik)'}

STRANKA PRAVI: {json.dumps(latest, ensure_ascii=False)}

TVOJA NALOGA:
1. Če stranka pozdravlja — toplo pozdravi, omeni da si na voljo, vprašaj kako lahko pomagaš.
2. Če stranka sprašuje o storitvah — odgovori direktno, opiši kar jo zanima.
3. Če stranka želi rezervirati NOV termin — pokliči salon_book_appointment. Vključi dodatke v polje 'dodatki'.
4. Če stranka želi dodati dopolnitev k OBSTOJEČI rezervaciji (že ima booking ID) — pokliči salon_add_addon. NE kliči salon_book_appointment.
5. Če stranka želi preklicati — pokliči salon_cancel_booking.
6. Če stranka želi osebje — pokliči salon_request_staff.
7. Če je stranka samo potrdila, se strinja, ali sprejema brez sprememb ("ok", "v redu", "bom potem brez", "super", "hvala") — NE kliči nobenega orodja. Samo kratko potrdi ali se zahvali.
8. Če stranka želi plačati, vpraša o ceni, ali želi depozit/predplačilo — pokliči salon_create_invoice z ustreznim zneskom in namenom. V odgovoru posreduj povezavo za plačilo.

POMEMBNO: Če stranka omenja dopolnitev ki je NI na seznamu za izbrano storitev — NE vključi je v booking. Orodje salon_book_appointment bo samo preverilo dodatke in vrnilo rezultat. Preberi njegovo sporočilo in ga posreduj stranki.

Bodi kratek (1-3 stavke), naraven, vikanje."""

    return prompt


def _run_tools_phase(state: QualificationGraphState, llm: LLMService):
    """Run LLM with tools, execute any tool calls, return (system, msgs, had_tools, blocked_booking)."""
    latest = state.get("latest_message", "")
    system = _build_agent_prompt(state)
    msgs = [{"role": "user", "content": json.dumps(latest, ensure_ascii=False)}]

    contact = json.loads(execute_tool("salon_check_contact", {}))
    has_contact = contact.get("ok")

    tools = SALON_TOOLS
    resp = llm.call_with_tools(system, msgs, tools, required=False)
    tcs = resp.get("tool_calls")
    all_tcs = []

    blocked_booking = False
    if tcs:
        if not has_contact:
            booking_tcs = [tc for tc in tcs if tc["name"] == "salon_book_appointment"]
            if booking_tcs:
                blocked_booking = True
                tcs = [tc for tc in tcs if tc["name"] != "salon_book_appointment"]

    if tcs:
        for tc in tcs:
            result = execute_tool(tc["name"], tc["args"])
            all_tcs.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
            if tc["name"] == "salon_book_appointment":
                r = json.loads(result)
                if r.get("potrjeno"):
                    state["booking_confirmed"] = True
                    state["booking_date"] = tc["args"].get("datum", "")
                    state["booking_time"] = tc["args"].get("ura", "")
                    state["last_booking_id"] = r.get("id")
            if tc["name"] == "salon_cancel_booking":
                r = json.loads(result)
                if r.get("preklicano"):
                    state["booking_confirmed"] = False

        for tc in all_tcs:
            msgs.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
            ]})
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": tc["result"]})

    if blocked_booking:
        msgs.append({"role": "user", "content": "POZOR: Stranka še nima kontakta. Ne smeš rezervirati brez kontakta. Vljudno prosi za telefonsko številko ali email."})

    # Guard: if no tool called but user message clearly asks for action (date + contact), force second pass
    if not all_tcs and has_contact:
        import re as _re
        has_date = bool(_re.search(r'\d{1,2}\.\d{1,2}\.|\d{4}-\d{2}-\d{2}|jutri|danes|pojutrišnjem|ponedeljek|torek|sredo|sreda|četrtek|petek|soboto|nedeljo|naslednji teden|ta teden', latest.lower()))
        has_time = bool(_re.search(r'ob\s+\d|\d{1,2}:\d{2}|\d{1,2}\.00|opoldne|dopoldne|popoldne|zjutraj|dopoldan|popoldan|enih|dveh|treh|štirih|petih|šestih|sedmih|osmih|devetih|desetih|enajstih|dvanajstih', latest.lower()))
        if has_date or has_time:
            msgs.append({"role": "user", "content": "MORAŠ poklicati orodje (salon_book_appointment). Ne smeš samo reči da boš uredil — dejansko pokliči orodje."})
            resp2 = llm.call_with_tools(system, msgs, [t for t in tools if t["function"]["name"] != "salon_check_contact"], required=True)
            tcs2 = resp2.get("tool_calls")
            if tcs2:
                second_results = []
                for tc in tcs2:
                    if not has_contact and tc["name"] == "salon_book_appointment":
                        continue
                    result = execute_tool(tc["name"], tc["args"])
                    second_results.append((tc, result))
                    all_tcs.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
                    if tc["name"] == "salon_book_appointment":
                        r = json.loads(result)
                        if r.get("potrjeno"):
                            state["booking_confirmed"] = True
                            state["booking_date"] = tc["args"].get("datum", "")
                            state["booking_time"] = tc["args"].get("ura", "")
                            state["last_booking_id"] = r.get("id")
                    if tc["name"] == "salon_cancel_booking":
                        r = json.loads(result)
                        if r.get("preklicano"):
                            state["booking_confirmed"] = False
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
        reply = "Dober dan! Kako vam lahko pomagam? 💆‍♀️"

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
    """Streaming variant — yields (state_dict, token) tuples during final reply."""
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
    
    # Stream final reply
    reply_parts = []
    for token in llm.stream_reply(system, msgs):
        if token:
            reply_parts.append(token)
            yield token
    
    reply = "".join(reply_parts).strip()
    if not reply:
        reply = state.get("decision", {}).get("reply", "") if "decision" in state else ""
    if not reply:
        reply = "Dober dan! Kako vam lahko pomagam? 💆‍♀️"
        yield reply  # yield fallback as single token

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
