"""
Analize tab — LLM-powered business intelligence endpoint.

POST /api/organizations/{org_id}/analize      — one-shot aggregated analysis
POST /api/organizations/{org_id}/analize/label — per-lead labeling
POST /api/organizations/{org_id}/analize/chat  — persona chat with LangGraph agent
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_db
from auth import get_current_user, User

router = APIRouter()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))


# ═══════════════════════════════════════════════════════════
#  Data queries (unchanged)
# ═══════════════════════════════════════════════════════════

async def _query_analytics(db: AsyncSession, org_id: int) -> dict:
    """Collect all analytics data from the DB."""
    leads_rows = (await db.execute(text("""
        SELECT id, sid, display_name, status, last_message_preview, last_message_at,
               qualification_score, qualifier_profile, takeover_active,
               created_at, updated_at
        FROM leads WHERE organization_id = :oid ORDER BY created_at
    """), {"oid": org_id})).fetchall()

    total_leads = len(leads_rows)
    open_chat = sum(1 for r in leads_rows if r[3] == "OPEN_CHAT")
    human_takeover = sum(1 for r in leads_rows if r[3] == "HUMAN_TAKEOVER")
    closed = sum(1 for r in leads_rows if r[3] == "CLOSED")
    survey = sum(1 for r in leads_rows if r[3] == "SURVEY")

    msg_counts = {}
    if total_leads > 0:
        lead_ids = [r[0] for r in leads_rows]
        msg_rows = (await db.execute(text("""
            SELECT lead_id, COUNT(*) as cnt,
                   SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as user_msgs,
                   SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) as bot_msgs
            FROM conversation_messages
            WHERE organization_id = :oid AND lead_id = ANY(:lids)
            GROUP BY lead_id
        """), {"oid": org_id, "lids": lead_ids})).fetchall()
        for row in msg_rows:
            msg_counts[row[0]] = {"total": row[1], "user": row[2] or 0, "bot": row[3] or 0}

    greeted = 0; asked_services = 0; asked_availability = 0; asked_booking = 0
    if total_leads > 0:
        all_msgs = (await db.execute(text("""
            SELECT cm.text FROM conversation_messages cm
            JOIN leads l ON cm.lead_id = l.id
            WHERE l.organization_id = :oid AND cm.role = 'user'
        """), {"oid": org_id})).fetchall()
        service_keywords = ["nega", "maska", "čiščenje", "storitev", "cena", "koliko stane", "ponujate", "imate", "delate", "nudite"]
        avail_keywords = ["prost", "termin", "kda", "teden", "jutri", "danes", "ponedeljek", "torek", "sredo", "četrtek", "petek"]
        book_keywords = ["rezerv", "želim", "bi se naročil", "bi se naročila", "hočem", "rabim termin"]
        for (msg_text,) in all_msgs:
            if not msg_text: continue
            lower = msg_text.lower()
            if any(w in lower for w in ["živjo", "dober dan", "zdravo", "pozdrav"]): greeted += 1
            if any(w in lower for w in service_keywords): asked_services += 1
            if any(w in lower for w in avail_keywords): asked_availability += 1
            if any(w in lower for w in book_keywords): asked_booking += 1

    bookings = (await db.execute(text("""
        SELECT id, service_name, booking_date, booking_time, duration_min, price_eur,
               status, addons, customer_name, customer_phone
        FROM bookings WHERE organization_id = :oid AND status != 'cancelled'
        ORDER BY booking_date, booking_time
    """), {"oid": org_id})).fetchall()

    booking_list = []; total_revenue = 0.0
    by_service: dict = {}; by_status: dict = {}; by_date: dict = {}; by_hour: dict = {}
    for b in bookings:
        price = float(b[5]) if b[5] else 0
        addons_raw = b[7]; addon_count = 0
        if addons_raw:
            try:
                addons_data = json.loads(addons_raw) if isinstance(addons_raw, str) else addons_raw
                addon_count = len(addons_data)
            except Exception: pass
        booking_list.append({
            "id": b[0], "service": b[1], "date": str(b[2]), "time": b[3],
            "duration_min": b[4], "price_eur": price, "status": b[6],
            "addon_count": addon_count, "customer": b[8], "phone": b[9],
        })
        total_revenue += price
        svc = b[1] or "unknown"; by_service[svc] = by_service.get(svc, 0) + 1
        st = b[6] or "confirmed"; by_status[st] = by_status.get(st, 0) + 1
        d = str(b[2]) if b[2] else "unknown"; by_date[d] = by_date.get(d, 0) + 1
        h = (b[3] or "00:00")[:2]; by_hour[h] = by_hour.get(h, 0) + 1

    total_addons = sum(b["addon_count"] for b in booking_list)
    bookings_with_addons = sum(1 for b in booking_list if b["addon_count"] > 0)
    today = datetime.now().strftime("%Y-%m-%d")
    today_bookings = [b for b in booking_list if b["date"] == today]
    today_revenue = sum(b["price_eur"] for b in today_bookings)

    return {
        "total_leads": total_leads,
        "by_status": {"OPEN_CHAT": open_chat, "HUMAN_TAKEOVER": human_takeover, "CLOSED": closed, "SURVEY": survey},
        "funnel": {"greeted": greeted, "asked_services": asked_services, "asked_availability": asked_availability, "asked_booking": asked_booking},
        "messages_per_lead": msg_counts,
        "total_bookings": len(booking_list),
        "booking_list": booking_list[:50],
        "total_revenue": round(total_revenue, 2),
        "by_service": by_service, "by_status": by_status,
        "by_date": {k: v for k, v in sorted(by_date.items())[:14]},
        "by_hour": {str(k): v for k, v in sorted(by_hour.items())},
        "total_addons": total_addons, "bookings_with_addons": bookings_with_addons,
        "today": {"date": today, "bookings": len(today_bookings), "revenue": round(today_revenue, 2)},
    }


def _run_llm_analysis(data: dict) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        return "❌ OpenAI/DeepSeek client not available."
    if not DEEPSEEK_API_KEY:
        return "❌ DEEPSEEK_API_KEY not set."

    system = """Ti si poslovni analitik za kozmetični salon Lepota & Sprostitev. 
Tvoj odgovor je v slovenščini. Bodi direkten, konkreten, brez floskul."""
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    user = f"""Analiziraj te podatke ... PODATKI:\n{data_json}\n\nVrni SAMO JSON, nič drugega."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat", temperature=0.3,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            timeout=60,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return json.dumps({"napaka": f"LLM analysis failed: {str(e)[:200]}"})


@router.post("/api/organizations/{org_id}/analize")
async def run_analize(org_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "PLATFORM_ADMIN" and user.organization_id != org_id:
        raise HTTPException(403, "Access denied")
    data = await _query_analytics(db, org_id)
    analysis_raw = _run_llm_analysis(data)
    try: analysis = json.loads(analysis_raw)
    except json.JSONDecodeError: analysis = {"surov_odgovor": analysis_raw}
    return {"ok": True, "data": data, "analysis": analysis}


# ═══════════════════════════════════════════════════════════
#  Per-lead labeling
# ═══════════════════════════════════════════════════════════

class LabelRequest(BaseModel):
    sid: str
    messages: list[dict]

_label_system = """Ti si analitik pogovorov za kozmetični salon.
Za vsak pogovor vrni SAMO JSON s temi oznakami:
{
  "je_rezerviral": true/false,
  "je_placal": true/false,
  "sentiment": "pozitiven / nevtralen / negativen / navdušen / razočaran",
  "osip_razlog": null če je rezerviral/a. Če ni, izberi: ghost_po_pozdravu, narobna_storitev, predrago, kontaktni_loop, izgubil_interes, drugo,
  "source": null ali kako je stranka našla salon: instagram, google, priporočilo, facebook, mimoidoči
}"""


def _label_one_lead(sid: str, messages: list[dict]) -> dict:
    if not DEEPSEEK_API_KEY:
        return {"napaka": "DEEPSEEK_API_KEY not set"}
    convo_text = "\n".join(
        f"[{'STRANKA' if m.get('role') == 'user' else 'RECEPTOR'}]: {m.get('text', '')}"
        for m in messages
    )
    user_prompt = f"Analiziraj ta pogovor. SID: {sid}\n\n{convo_text}\n\nVrni SAMO JSON z oznakami, nič drugega."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat", temperature=0.2,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": _label_system}, {"role": "user", "content": user_prompt}],
            timeout=30,
        )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception as e:
        return {"napaka": str(e)[:200]}


@router.post("/api/organizations/{org_id}/analize/label")
async def label_lead(org_id: int, body: LabelRequest, user: User = Depends(get_current_user)):
    if user.role != "PLATFORM_ADMIN" and user.organization_id != org_id:
        raise HTTPException(403, "Access denied")
    labels = _label_one_lead(body.sid, body.messages)
    return {"sid": body.sid, "labels": labels}


# ═══════════════════════════════════════════════════════════
#  Persona chat — LangGraph agent with tools
# ═══════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    persona_id: str
    message: str
    leads: list[dict] = []
    history: list[dict] = []  # [{role, text}, ...]

PERSONA_PROMPTS = {
    "poslovni": """Ti si Poslovni svetovalec za kozmetični salon Lepota & Sprostitev.
Si direkten, konkreten, brez floskul. Govoriš slovenščino.

Na voljo imaš ORODJA za delo s podatki o strankah:
- search_leads(filters) — filtriraj lead-e. Primer: search_leads({"osip_razlog": "predrago"})
- get_lead(sid) — polni podatki enega lead-a
- get_stats() — agregirana statistika
- count_by(field) — grupiraj po katerikoli lastnosti

VEDNO UPORABI ORODJA. Ne ugibaj.""",

    "marketingar": """Ti si Marketingar za kozmetični salon Lepota & Sprostitev.
Specializiran/a si za konverzije, jezik, kanale in A/B testiranje. Govoriš slovenščino.

Na voljo imaš ORODJA: search_leads, get_lead, get_stats, count_by.
Si oster/a in natančen/a. VEDNO UPORABI ORODJA.""",

    "cenovni-lovec": """Ti si Cenovni lovec — simuliraš stranko, ki ji je cena NAJPOMEMBNEJŠA.
Govoriš sproščeno slovenščino. Vedno vprašaš po ceni, primerjaš s konkurenco.
Odgovarjaš SAMO kot stranka.""",

    "ig-brskalka": """Ti si Instagram brskalka — našel/našla si salon na Instagramu.
Všeč so ti njihove objave. Govoriš sproščeno, uporabljaš 'ful', 'top'.
Odgovarjaš SAMO kot stranka.""",

    "vip": """Ti si VIP zahtevnež — hočeš najboljše kar salon ponuja. Cena ni pomembna.
Govoriš samozavestno, vljudno ampak zahtevno. Odgovarjaš SAMO kot stranka.""",
}


# ═══════════════════════════════════════════════════════════
#  ANALYZE TOOLS — completely separate from salon tools
# ═══════════════════════════════════════════════════════════

ANALYZE_TOOLS = [
    {"type": "function", "function": {
        "name": "search_leads",
        "description": "Filtriraj lead-e po katerikoli lastnosti. Vrne SID, ime, oznake. Primer: search_leads({\"osip_razlog\": \"predrago\", \"source\": \"instagram\"}) vrne vse ki so odpadli zaradi cene in prišli z Instagrama.",
        "parameters": {"type": "object", "properties": {
            "filters": {"type": "object", "description": "JSON objekt s filtri. Lahko filtriraš po: booked (true/false), osip_razlog, source, sentiment, discussed_services, eur_amount ({\"min\": N, \"max\": N}), turn_count"},
        }, "required": ["filters"]},
    }},
    {"type": "function", "function": {
        "name": "get_lead",
        "description": "Pridobi vse podrobnosti enega lead-a po SID-u (npr. 'sim-050').",
        "parameters": {"type": "object", "properties": {
            "sid": {"type": "string", "description": "SID lead-a"},
        }, "required": ["sid"]},
    }},
    {"type": "function", "function": {
        "name": "get_stats",
        "description": "Vrni agregirano statistiko: število, konverzija %, skupni EUR, povprečni EUR, osip po razlogih, viri, sentiment, storitve.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "count_by",
        "description": "Preštej lead-e grupirane po polju. Primer: count_by(\"osip_razlog\") vrne {\"predrago\": 11, \"ghost_po_pozdravu\": 38, ...}.",
        "parameters": {"type": "object", "properties": {
            "field": {"type": "string", "description": "Polje: osip_razlog, source, sentiment, booked, discussed_services"},
        }, "required": ["field"]},
    }},
]


# ═══════════════════════════════════════════════════════════
#  Tool execution (same LLMService pattern as visitor chat)
# ═══════════════════════════════════════════════════════════

def _execute_analyze_tool(name: str, args: dict, leads: list[dict]) -> str:
    """Execute an analyze tool against the leads array. Mirror of app/qualification/tools.execute_tool."""
    if name == "get_stats":
        total = len(leads)
        booked = [l for l in leads if l.get('booked')]
        not_booked = [l for l in leads if not l.get('booked')]
        booked_eur = sum(l.get('eur_amount', 0) or 0 for l in booked)
        avg_eur = round(booked_eur / max(len(booked), 1))
        osip = {}
        for l in not_booked:
            r = ((l.get('labels') or {}).get('osip_razlog')) or 'neznano'
            osip[r] = osip.get(r, 0) + 1
        sources = {}
        for l in leads:
            s = ((l.get('labels') or {}).get('source')) or 'neznano'
            sources[s] = sources.get(s, 0) + 1
        sents = {}
        for l in leads:
            s = ((l.get('labels') or {}).get('sentiment')) or 'neznano'
            sents[s] = sents.get(s, 0) + 1
        svcs = {}
        for l in leads:
            for s in (l.get('discussed_services') or []):
                svcs[s] = svcs.get(s, 0) + 1
        addon_count = sum(1 for l in booked if l.get('addons') and len(l.get('addons', [])) > 0)
        return json.dumps({
            "total": total, "booked": len(booked), "not_booked": len(not_booked),
            "conversion_pct": round(len(booked) / max(total, 1) * 100),
            "total_eur": booked_eur, "avg_eur_per_booking": avg_eur,
            "osip_razlogi": osip, "viri": sources, "sentiment": sents, "storitve": svcs,
            "z_dodatki": f"{addon_count}/{len(booked)}",
        }, ensure_ascii=False)

    elif name == "count_by":
        field = args.get("field", "")
        counts: dict[str, int] = {}
        if field in ("osip_razlog", "source", "sentiment"):
            for l in leads:
                val = ((l.get('labels') or {}).get(field)) or 'neznano'
                counts[val] = counts.get(val, 0) + 1
        elif field == "booked":
            for l in leads:
                val = str(l.get('booked', False))
                counts[val] = counts.get(val, 0) + 1
        elif field == "discussed_services":
            for l in leads:
                for s in (l.get('discussed_services') or []):
                    counts[s] = counts.get(s, 0) + 1
        else:
            return json.dumps({"napaka": f"Neznano polje: {field}"})
        return json.dumps(counts, ensure_ascii=False)

    elif name == "search_leads":
        filters = args.get("filters", {})
        # Handle double-encoded JSON strings from LLM
        if isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except Exception:
                filters = {}
        if not isinstance(filters, dict):
            filters = {}
        results = []
        for l in leads:
            match = True
            for k, v in filters.items():
                if k == "discussed_services":
                    svcs = l.get("discussed_services") or []
                    if isinstance(v, str) and v not in svcs: match = False
                    elif isinstance(v, list) and not any(s in svcs for s in v): match = False
                elif k in ("osip_razlog", "source", "sentiment"):
                    if ((l.get('labels') or {}).get(k)) != v: match = False
                elif k == "booked":
                    if l.get("booked") != v: match = False
                elif k == "eur_amount":
                    amt = l.get("eur_amount") or 0
                    if isinstance(v, dict):
                        if "min" in v and amt < v["min"]: match = False
                        if "max" in v and amt > v["max"]: match = False
                    elif amt != v: match = False
                elif k == "turn_count":
                    tc = l.get("turn_count") or 0
                    if isinstance(v, dict):
                        if "min" in v and tc < v["min"]: match = False
                        if "max" in v and tc > v["max"]: match = False
                    elif tc != v: match = False
                else:
                    if l.get(k) != v: match = False
                if not match: break
            if match:
                labels = l.get('labels') or {}
                results.append({
                    "sid": l.get("sid"), "name": l.get("name"), "booked": l.get("booked"),
                    "eur_amount": l.get("eur_amount"), "turn_count": l.get("turn_count"),
                    "osip_razlog": labels.get("osip_razlog"), "source": labels.get("source"),
                    "sentiment": labels.get("sentiment"),
                    "discussed_services": l.get("discussed_services"),
                    "booking_time": l.get("booking_time"),
                })
        limit = 30
        out = json.dumps(results[:limit], ensure_ascii=False)
        if len(results) > limit:
            out += f"\n... (skupaj {len(results)} zadetkov, prikazanih prvih {limit})"
        return out

    elif name == "get_lead":
        sid = args.get("sid", "")
        for l in leads:
            if l.get("sid") == sid:
                return json.dumps(l, ensure_ascii=False, default=str)
        return json.dumps({"napaka": f"Lead '{sid}' ne obstaja"})

    return json.dumps({"napaka": f"Neznano orodje: {name}"})


# ═══════════════════════════════════════════════════════════
#  Agent loop — same pattern as app/qualification/graph.py
# ═══════════════════════════════════════════════════════════

def _run_agent(system_prompt: str, user_message: str, history: list[dict], leads: list[dict]) -> str:
    """Run tool-calling loop using LLMService (same as visitor chat)."""
    from app.services.llm_service import LLMService

    llm = LLMService()

    # Build messages: history + current message
    msgs = []
    for h in history:
        role = "user" if h.get("role") == "user" else "assistant"
        msgs.append({"role": role, "content": h.get("text", "")})
    msgs.append({"role": "user", "content": user_message})

    # Tool loop: LLM calls tools, we execute, LLM sees results, answers
    max_loops = 4
    for _ in range(max_loops):
        resp = llm.call_with_tools(system_prompt, msgs, ANALYZE_TOOLS, required=False)
        if resp.get("text"):
            return resp["text"]
        tcs = resp.get("tool_calls")
        if not tcs:
            break
        # Execute tools, add results
        for tc in tcs:
            try:
                result = _execute_analyze_tool(tc["name"], tc["args"], leads)
            except Exception as e:
                result = json.dumps({"napaka": str(e)[:200]})
            msgs.append({"role": "assistant", "content": None, "tool_calls": [{
                "id": tc["id"], "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}
            }]})
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    # Final answer — LLM sees all tool results now
    final = llm.call_with_tools(system_prompt, msgs, ANALYZE_TOOLS, required=False)
    return final.get("text", "") or "Oprosti, nisem mogel/a obdelati tega vprašanja."


@router.post("/api/organizations/{org_id}/analize/chat")
async def persona_chat(org_id: int, body: ChatRequest, user: User = Depends(get_current_user)):
    if user.role != "PLATFORM_ADMIN" and user.organization_id != org_id:
        raise HTTPException(403, "Access denied")

    system = PERSONA_PROMPTS.get(body.persona_id, PERSONA_PROMPTS["poslovni"])
    is_advisor = body.persona_id in ("poslovni", "marketingar")

    try:
        if is_advisor and body.leads:
            reply = _run_agent(system, body.message, body.history, body.leads)
        else:
            from openai import OpenAI
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            msgs = [{"role": "system", "content": system}]
            for h in body.history:
                role = "user" if h.get("role") == "user" else "assistant"
                msgs.append({"role": role, "content": h.get("text", "")})
            msgs.append({"role": "user", "content": body.message})
            resp = client.chat.completions.create(
                model="deepseek-chat", temperature=0.7, messages=msgs, timeout=30,
            )
            reply = resp.choices[0].message.content.strip()

        return {"reply": reply}
    except Exception as e:
        return {"reply": f"Napaka: {str(e)[:200]}"}
