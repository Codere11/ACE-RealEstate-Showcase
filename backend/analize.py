"""
Analize tab — LLM-powered business intelligence endpoint.

Queries real lead, message, and booking data from PostgreSQL,
sends it to DeepSeek, and returns actionable insights.
No LangChain. No external tools. Just SQL + LLM.

POST /api/organizations/{org_id}/analize
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_db
from auth import get_current_user, User

router = APIRouter()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))


# ═══════════════════════════════════════════════════════════
#  Data queries
# ═══════════════════════════════════════════════════════════

async def _query_analytics(db: AsyncSession, org_id: int) -> dict:
    """Collect all analytics data from the DB."""

    # ── Leads ──
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

    # ── Messages per lead ──
    msg_counts = {}
    if total_leads > 0:
        lead_ids = [r[0] for r in leads_rows]
        # Fetch message counts in one query
        msg_rows = (await db.execute(text("""
            SELECT lead_id, COUNT(*) as cnt, 
                   SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as user_msgs,
                   SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) as bot_msgs
            FROM conversation_messages
            WHERE organization_id = :oid AND lead_id = ANY(:lids)
            GROUP BY lead_id
        """), {"oid": org_id, "lids": lead_ids})).fetchall()
        for row in msg_rows:
            msg_counts[row[0]] = {
                "total": row[1], "user": row[2] or 0, "bot": row[3] or 0,
            }

    # ── Funnel stages (keyword-based) ──
    greeted = 0
    asked_services = 0
    asked_availability = 0
    asked_booking = 0

    if total_leads > 0:
        all_msgs = (await db.execute(text("""
            SELECT cm.text FROM conversation_messages cm
            JOIN leads l ON cm.lead_id = l.id
            WHERE l.organization_id = :oid AND cm.role = 'user'
        """), {"oid": org_id})).fetchall()

        service_keywords = ["nega", "maska", "čiščenje", "storitev", "cena", "koliko stane",
                          "ponujate", "imate", "delate", "nudite"]
        avail_keywords = ["prost", "termin", "kda", "teden", "jutri", "danes",
                        "ponedeljek", "torek", "sredo", "četrtek", "petek"]
        book_keywords = ["rezerv", "želim", "bi se naročil", "bi se naročila",
                       "hočem", "rabim termin"]

        for (msg_text,) in all_msgs:
            if not msg_text:
                continue
            lower = msg_text.lower()
            if any(w in lower for w in ["živjo", "dober dan", "zdravo", "pozdrav"]):
                greeted += 1
            if any(w in lower for w in service_keywords):
                asked_services += 1
            if any(w in lower for w in avail_keywords):
                asked_availability += 1
            if any(w in lower for w in book_keywords):
                asked_booking += 1

    # ── Bookings ──
    bookings = (await db.execute(text("""
        SELECT id, service_name, booking_date, booking_time, duration_min, price_eur,
               status, addons, customer_name, customer_phone
        FROM bookings WHERE organization_id = :oid AND status != 'cancelled'
        ORDER BY booking_date, booking_time
    """), {"oid": org_id})).fetchall()

    booking_list = []
    total_revenue = 0.0
    by_service: dict = {}
    by_status: dict = {}
    by_date: dict = {}
    by_hour: dict = {}

    for b in bookings:
        price = float(b[5]) if b[5] else 0
        addons_raw = b[7]
        addon_count = 0
        if addons_raw:
            try:
                addons_data = json.loads(addons_raw) if isinstance(addons_raw, str) else addons_raw
                addon_count = len(addons_data)
            except Exception:
                pass

        booking_list.append({
            "id": b[0], "service": b[1], "date": str(b[2]), "time": b[3],
            "duration_min": b[4], "price_eur": price,
            "status": b[6], "addon_count": addon_count,
            "customer": b[8], "phone": b[9],
        })
        total_revenue += price
        svc = b[1] or "unknown"
        by_service[svc] = by_service.get(svc, 0) + 1
        st = b[6] or "confirmed"
        by_status[st] = by_status.get(st, 0) + 1
        d = str(b[2]) if b[2] else "unknown"
        by_date[d] = by_date.get(d, 0) + 1
        h = (b[3] or "00:00")[:2]
        by_hour[h] = by_hour.get(h, 0) + 1

    # ── Add-on stats ──
    total_addons = sum(b["addon_count"] for b in booking_list)
    bookings_with_addons = sum(1 for b in booking_list if b["addon_count"] > 0)

    # ── Today/tomorrow context ──
    today = datetime.now().strftime("%Y-%m-%d")
    today_bookings = [b for b in booking_list if b["date"] == today]
    today_revenue = sum(b["price_eur"] for b in today_bookings)

    return {
        "total_leads": total_leads,
        "by_status": {"OPEN_CHAT": open_chat, "HUMAN_TAKEOVER": human_takeover,
                      "CLOSED": closed, "SURVEY": survey},
        "funnel": {"greeted": greeted, "asked_services": asked_services,
                   "asked_availability": asked_availability, "asked_booking": asked_booking},
        "messages_per_lead": msg_counts,
        "total_bookings": len(booking_list),
        "booking_list": booking_list[:50],  # limit to avoid huge prompts
        "total_revenue": round(total_revenue, 2),
        "by_service": by_service,
        "by_status": by_status,
        "by_date": {k: v for k, v in sorted(by_date.items())[:14]},
        "by_hour": {str(k): v for k, v in sorted(by_hour.items())},
        "total_addons": total_addons,
        "bookings_with_addons": bookings_with_addons,
        "today": {"date": today, "bookings": len(today_bookings),
                  "revenue": round(today_revenue, 2)},
    }


# ═══════════════════════════════════════════════════════════
#  LLM analysis
# ═══════════════════════════════════════════════════════════

def _run_llm_analysis(data: dict) -> str:
    """Send structured analytics data to DeepSeek, get insights back."""
    try:
        from openai import OpenAI
    except ImportError:
        return "❌ OpenAI/DeepSeek client not available."

    if not DEEPSEEK_API_KEY:
        return "❌ DEEPSEEK_API_KEY not set."

    system = """Ti si poslovni analitik za kozmetični salon Lepota & Sprostitev. 
Tvoj odgovor je v slovenščini. Bodi direkten, konkreten, brez floskul.
Vsaka tvoja trditev mora temeljiti na številkah iz podatkov.
Če so podatki pomanjkljivi, to povej direktno."""

    data_json = json.dumps(data, ensure_ascii=False, indent=2)

    user = f"""Analiziraj te podatke iz kozmetičnega salona. Vrni JSON objekt s točno temi ključi:

1. "funnel": kratek opis kje ljudje odpadajo v prodajnem lijaku (pozdravi → storitve → termini → rezervacije). Vrni tudi "stages" array: [{{"stage": "pozdrav", "count": N}}, ...]

2. "segmenti": opiši tipe strank ki jih vidiš v podatkih. Vrni "groups" array: [{{"name": "ime segmenta", "count": N, "desc": "opis"}}] npr. "okenski brskalci", "pripravljeni kupci", "zbiralci cen". Bodi kreativen ampak natančen.

3. "koledar": kako poln je koledar, kateri dnevi/ure so prazni, kateri polni. Vrni "utilization": število 0-100, "prazne_ure": [...], "najbolj_zasedeni": [...]

4. "prihodki": projekcija prihodkov na podlagi obstoječih rezervacij. Vrni "potrjeno_eur": število, "povprecno_na_rezervacijo": število, "danes_eur": število.

5. "konverzije": katera storitev najbolj konvertira, kateri čas dneva. Vrni "najboljsa_storitev": string, "najboljsa_ura": string.

6. "priporocila": 3-5 KONKRETNIH priporočil za izboljšanje. NE splošnih floskul. Vsako mora imeti "ukrep": kaj narediti in "vpliv": zakaj bi pomagalo. Temelji na številkah.

7. "povzetek": en stavek — najpomembnejša ugotovitev.

PODATKI:
{data_json}

Vrni SAMO JSON, nič drugega."""

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            timeout=60,
        )
        content = resp.choices[0].message.content.strip()
        return content
    except Exception as e:
        return json.dumps({"napaka": f"LLM analysis failed: {str(e)[:200]}"})


# ═══════════════════════════════════════════════════════════
#  Endpoint
# ═══════════════════════════════════════════════════════════

@router.post("/api/organizations/{org_id}/analize")
async def run_analize(
    org_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Auth: platform admin or org member
    if user.role != "PLATFORM_ADMIN" and user.organization_id != org_id:
        raise HTTPException(403, "Access denied")

    # Query
    data = await _query_analytics(db, org_id)

    # LLM
    analysis_raw = _run_llm_analysis(data)

    # Parse
    try:
        analysis = json.loads(analysis_raw)
    except json.JSONDecodeError:
        analysis = {"surov_odgovor": analysis_raw}

    return {
        "ok": True,
        "data": data,
        "analysis": analysis,
    }


# ═══════════════════════════════════════════════════════════
#  Per-lead labeling — called by frontend after loading messages
# ═══════════════════════════════════════════════════════════

from pydantic import BaseModel

class LabelRequest(BaseModel):
    sid: str
    messages: list[dict]  # [{role, text}, ...]

_label_system = """Ti si analitik pogovorov za kozmetični salon.
Za vsak pogovor vrni SAMO JSON s temi oznakami:

{
  "je_rezerviral": true/false — ali je stranka rezervirala termin,
  "je_placal": true/false — ali je stranka plačala,
  "sentiment": "pozitiven / nevtralen / negativen / navdušen / razočaran"
}"""


def _label_one_lead(sid: str, messages: list[dict]) -> dict:
    """Send one lead's messages to DeepSeek, return labels."""
    if not DEEPSEEK_API_KEY:
        return {"napaka": "DEEPSEEK_API_KEY not set"}

    convo_text = "\n".join(
        f"[{'STRANKA' if m.get('role') == 'user' else 'RECEPTOR' if m.get('role') == 'assistant' else m.get('role', '?').upper()}]: {m.get('text', '')}"
        for m in messages
    )

    user_prompt = f"""Analiziraj ta pogovor. SID: {sid}

{convo_text}

Vrni SAMO JSON z oznakami, nič drugega."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _label_system},
                {"role": "user", "content": user_prompt},
            ],
            timeout=30,
        )
        content = resp.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        return {"napaka": str(e)[:200]}


@router.post("/api/organizations/{org_id}/analize/label")
async def label_lead(
    org_id: int,
    body: LabelRequest,
    user: User = Depends(get_current_user),
):
    if user.role != "PLATFORM_ADMIN" and user.organization_id != org_id:
        raise HTTPException(403, "Access denied")

    labels = _label_one_lead(body.sid, body.messages)
    return {"sid": body.sid, "labels": labels}
