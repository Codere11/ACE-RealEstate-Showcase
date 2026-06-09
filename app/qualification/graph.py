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


def _build_agent_prompt(state: QualificationGraphState) -> str:
    latest = state.get("latest_message", "")
    recent = state.get("recent_messages", []) or []
    last_booking_id = state.get("last_booking_id")

    biz = json.loads(execute_tool("ace_get_context", {}))
    contact = json.loads(execute_tool("ace_check_contact", {}))
    has_contact = contact.get("ok")

    if recent:
        history = "\n".join(
            f"  {m.get('role','?')}: {m.get('text','')[:300]}"
            for m in recent
        )
    else:
        history = "(prazen - prvi stik)"

    call_info = f"Klic ze dogovorjen (ID: {last_booking_id})" if last_booking_id else ""

    prompt = f"""Ti si AI Svetovalec za ACE - pomagas podjetjem avtomatizirati sprejem strank z AI-jem.
ACE ponuja: AI Reception, Analytics, Integrations, AI Lead Scoring.
Si sprošcen, direkten, pogovoren - kot dober prodajni svetovalec na kavi. Govoris naravno slovenscino.
VIKAJ (vi, vas, vas), nikoli tikaj.

DELOVNI CAS: {biz.get('status','')} ({biz.get('delovni_cas','')})
Naslednji delovni dan: {biz.get('naslednji_delovni_dan','')}
Kontakt: {'IMA' if has_contact else 'SE NIMA - vprasaj ko pogovor stece, ne takoj'}
{call_info}

CELOTEN POGOVOR (tvoj spomin - beri ga!):
{history}

STRANKA PRAVI: {json.dumps(latest, ensure_ascii=False)}

NALOGA:
- Preberi celoten pogovor. NE ponavljaj vprasanj na katere je stranka ze odgovorila!
- Prvi stik: pozdravi, na kratko povej kaj ACE pocne, vprasaj kaj jih je pripeljalo.
- Skozi pogovor spoznavaj: kaj potrebujejo, tip podjetja, obseg, kaj zdaj uporabljajo.
- Kontakt vprasaj sele po 2-3 izmenjavah, ne takoj.
- Ko imas dovolj info IN kontakt - ponudi klic (ace_schedule_call).
- Ce je zaprto - povej da se slisimo naslednji delovni dan.
- Ce stranka potrdi ("ok", "super", "ja") - kratko potrdi, ne sprasuj naprej.

Bodi sproscen, 1-3 stavke. Ne ponavljaj se. Ne izmisljuj si cen."""

    return prompt


def _run_tools_phase(state: QualificationGraphState, llm: LLMService):
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
        msgs.append({"role": "user", "content": "POZOR: Stranka se nima kontakta. Ne smes rezervirati klica brez kontakta. Vljudno prosi za telefonsko stevilko ali email."})

    booking_tool_names = {"ace_schedule_call"}
    had_booking_tool = any(tc["name"] in booking_tool_names for tc in all_tcs)
    already_booked = bool(state.get("last_booking_id"))
    if not had_booking_tool and has_contact and not already_booked:
        import re as _re
        has_date = bool(_re.search(r'\d{1,2}\.\d{1,2}\.|\d{4}-\d{2}-\d{2}|jutri|danes|pojutrisnjem|ponedeljek|torek|sredo|sreda|cetrtek|petek|soboto|nedeljo|naslednji teden|ta teden', latest.lower()))
        has_time = bool(_re.search(r'ob\s+\d|\d{1,2}:\d{2}|\d{1,2}\.00|opoldne|dopoldne|popoldne|zjutraj|dopoldan|popoldan|enih|dveh|treh|stirih|petih|sestih|sedmih|osmih|devetih|desetih|enajstih|dvanajstih', latest.lower()))
        if has_date or has_time:
            msgs.append({"role": "user", "content": "MORAS poklicati orodje (ace_schedule_call). Ne smes samo reci da bos uredil - dejansko poklici orodje."})
            resp2 = llm.call_with_tools(system, msgs, [t for t in tools if t["function"]["name"] != "ace_check_contact"], required=True)
            tcs2 = resp2.get("tool_calls")
            if tcs2:
                for tc in tcs2:
                    if not has_contact and tc["name"] == "ace_schedule_call":
                        continue
                    result = execute_tool(tc["name"], tc["args"])
                    all_tcs.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "result": result})
                    if tc["name"] == "ace_schedule_call":
                        r = json.loads(result)
                        if r.get("potrjeno"):
                            state["booking_confirmed"] = True
                            state["booking_date"] = tc["args"].get("datum", "")
                            state["booking_time"] = tc["args"].get("ura", "")
                            state["last_booking_id"] = r.get("id")
                    msgs.append({"role": "assistant", "content": None, "tool_calls": [
                        {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                    ]})
                    msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    return system, msgs, bool(all_tcs), blocked_booking


def _agent_node(state: QualificationGraphState) -> QualificationGraphState:
    llm = LLMService()
    latest = state.get("latest_message", "")

    system, msgs, had_tools, blocked_booking = _run_tools_phase(state, llm)

    reply = llm.call_json_response(system, msgs)
    reply = _unwrap_reply(reply)
    if not reply:
        fallback_user = json.dumps(latest, ensure_ascii=False)
        reply = llm.call_text(system, fallback_user)
    if not reply:
        reply = "Hej! Smo ACE. Kako vam lahko pomagamo?"

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

    system, msgs, tcs_executed, blocked_booking = _run_tools_phase(state, llm)

    latest = state.get("latest_message", "")
    reply = ""

    if tcs_executed:
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
            reply = "Hej! Smo ACE. Kako vam lahko pomagamo?"
        for ch in reply:
            yield ch
    else:
        stream_msgs = [{"role": "user", "content": json.dumps(latest, ensure_ascii=False)}]
        for token in llm.stream_reply(system, stream_msgs):
            if token:
                reply += token
                yield token
        reply = reply.strip()
        if not reply:
            reply = "Hej! Smo ACE. Kako vam lahko pomagamo?"
            yield reply

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
