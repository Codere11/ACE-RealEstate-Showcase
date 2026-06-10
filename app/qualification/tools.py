"""ACE B2B tools — business discovery, contact capture, call scheduling."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger("ace.tools")

# ── Business hours ──

OPEN_HOUR = 9
CLOSE_HOUR = 17

# ── DB context (set by backend before graph runs) ──
_db_ctx: Optional[dict] = None

def set_db_context(org_id: int, sid: str, lead_phone: Optional[str] = None, lead_email: Optional[str] = None):
    global _db_ctx
    _db_ctx = {"org_id": org_id, "sid": sid, "lead_phone": lead_phone, "lead_email": lead_email}

def _is_open() -> bool:
    now = datetime.now()
    return OPEN_HOUR <= now.hour < CLOSE_HOUR and now.weekday() < 5

def _status_text() -> str:
    return f"OPEN (until {CLOSE_HOUR}:00)" if _is_open() else f"CLOSED (open Mon–Fri {OPEN_HOUR}:00–{CLOSE_HOUR}:00)"

def _next_working_day() -> str:
    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════
#  Tools the LLM can call
# ═══════════════════════════════════════════════════════════

ACE_TOOLS = [
    {"type": "function", "function": {
        "name": "ace_get_context",
        "description": "Get current business context: open/closed status, working hours, next working day.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "ace_check_contact",
        "description": "Check if we already have the visitor's contact info (phone or email). If false, do NOT schedule a call — first politely ask for a phone number or email.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "ace_schedule_call",
        "description": "Rezerviraj termin za klic s stranko. Pokliči to takoj ko stranka želi termin — ne sprašuj, kar rezerviraj. Deluje tudi brez kontaktnih podatkov. Trajanje: 30 minut.",
        "parameters": {"type": "object", "properties": {
            "datum": {"type": "string", "description": "Datum v obliki YYYY-MM-DD. Lahko izračunaš: danes je " + datetime.now().strftime('%Y-%m-%d') + ". Naslednji torek = " + _next_working_day()},
            "ura": {"type": "string", "description": "Ura v obliki HH:MM, npr. '11:00' ali '14:00'"},
            "ime": {"type": "string", "description": "Ime obiskovalca"},
        }, "required": ["datum", "ura"]},
    }},
    {"type": "function", "function": {
        "name": "ace_request_team",
        "description": "Request a human team member to join the conversation LIVE. ONLY use this during working hours (Mon-Fri 9-17). Use when the lead is a good fit and would benefit from talking to a real person. During non-working hours, use ace_schedule_call instead to schedule a call for the next working day.",
        "parameters": {"type": "object", "properties": {
            "razlog": {"type": "string", "description": "Brief reason for the request"},
        }, "required": ["razlog"]},
    }},
    {"type": "function", "function": {
        "name": "ace_update_profile",
        "description": "Record what you learned about the prospect. Call this whenever the visitor shares useful information. You can update one or more fields at once. Only include fields you actually learned this turn.",
        "parameters": {"type": "object", "properties": {
            "use_case": {"type": "string", "description": "What they need — which ACE product, what problem they're solving"},
            "company_type": {"type": "string", "description": "Type of company / industry / size"},
            "scale": {"type": "string", "description": "Scale — how many customers, calls, users per day"},
            "current_system": {"type": "string", "description": "What they currently use for customer reception"},
            "timeline": {"type": "string", "description": "When they need a solution by"},
            "business_name": {"type": "string", "description": "The visitor's business or company name"},
            "budget": {"type": "string", "description": "Budget range or amount the prospect mentioned"},
            "problem": {"type": "string", "description": "The core problem or pain point they want to solve"},
        }, "required": []},
    }},
]


def _parse_date(datum: str) -> str:
    """Parse relative date strings into YYYY-MM-DD."""
    from datetime import datetime, timedelta
    today = datetime.now()
    datum_lower = datum.lower().strip()
    if datum_lower in ('jutri', 'jutrišnjem'):
        d = today + timedelta(days=1)
        return d.strftime("%Y-%m-%d")
    if datum_lower in ('pojutrišnjem',):
        d = today + timedelta(days=2)
        return d.strftime("%Y-%m-%d")
    day_map = {'ponedeljek': 0, 'pon': 0, 'torek': 1, 'tor': 1, 'sredo': 2, 'sreda': 2, 'sre': 2,
               'četrtek': 3, 'cetrtek': 3, 'čet': 3, 'cet': 3, 'petek': 4, 'pet': 4,
               'soboto': 5, 'sobota': 5, 'sob': 5, 'nedeljo': 6, 'nedelja': 6, 'ned': 6}
    for day_name, target_dow in day_map.items():
        if day_name in datum_lower:
            current_dow = today.weekday()
            days_ahead = (target_dow - current_dow) % 7
            if days_ahead == 0:
                days_ahead = 7
            d = today + timedelta(days=days_ahead)
            return d.strftime("%Y-%m-%d")
    import re
    if re.match(r'^\d{4}-\d{2}-\d{2}$', datum.strip()):
        return datum.strip()
    if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', datum.strip()):
        parts = datum.strip().split('.')
        return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return datum


def _parse_time(ura: str) -> str:
    """Parse time strings like 'enajstih', 'opoldne' into HH:MM."""
    import re
    ura_lower = ura.lower().strip()
    if re.match(r'^\d{1,2}:\d{2}$', ura.strip()):
        return ura.strip()
    time_map = {
        'enih': '13:00', 'ene': '13:00', 'dveh': '14:00', 'dve': '14:00',
        'treh': '15:00', 'tri': '15:00', 'štirih': '16:00', 'stirih': '16:00',
        'petih': '17:00', 'pet': '17:00', 'šestih': '18:00', 'sestih': '18:00',
        'sedmih': '19:00', 'sedem': '19:00', 'osmih': '20:00', 'osem': '20:00',
        'devetih': '09:00', 'devet': '09:00', 'desetih': '10:00', 'deset': '10:00',
        'enajstih': '11:00', 'enajst': '11:00', 'dvanajstih': '12:00', 'dvanajst': '12:00',
        'opoldne': '12:00', 'opoldan': '12:00', 'opoldneva': '12:00',
        'dopoldne': '10:00', 'dopoldan': '10:00', 'popoldne': '15:00', 'popoldan': '15:00',
        'zjutraj': '08:00', 'zvecer': '19:00', 'zvečer': '19:00',
    }
    for key, val in time_map.items():
        if key in ura_lower:
            return val
    # Try to extract digits
    digits = re.findall(r'\d+', ura)
    if digits:
        h = int(digits[0])
        return f"{h:02d}:00"
    return ura


def execute_tool(name: str, args: dict) -> str:
    try:
        if name == "ace_get_context":
            today = datetime.now().strftime("%Y-%m-%d")
            return json.dumps({
                "status": _status_text(), "odprto": _is_open(),
                "delovni_cas": f"Mon–Fri {OPEN_HOUR}:00–{CLOSE_HOUR}:00",
                "danes": today,
                "naslednji_delovni_dan": _next_working_day(),
            }, ensure_ascii=False)

        if name == "ace_check_contact":
            if not _db_ctx:
                return json.dumps({"ok": True, "sporocilo": "Contact checking unavailable — proceed."}, ensure_ascii=False)
            has_contact = bool(_db_ctx.get("lead_phone") or _db_ctx.get("lead_email"))
            if has_contact:
                return json.dumps({"ok": True, "ima_kontakt": True, "sporocilo": "Visitor has provided contact info."}, ensure_ascii=False)
            return json.dumps({"ok": False, "ima_kontakt": False, "sporocilo": "VISITOR HAS NO CONTACT. Politely ask for a phone number or email before scheduling a call."}, ensure_ascii=False)

        if name == "ace_schedule_call":
            datum = _parse_date(args.get("datum", ""))
            ura_raw = args.get("ura", "")
            ura = _parse_time(ura_raw)
            ime = args.get("ime", "Visitor")

            if not _db_ctx:
                return json.dumps({"potrjeno": False, "sporocilo": "Unable to save booking — database not available."}, ensure_ascii=False)

            booking_id = None
            try:
                from app.core.db import SessionLocal
                from sqlalchemy import text
                with SessionLocal() as db:
                    # Look up lead_id
                    lead_id = None
                    sid = _db_ctx.get("sid")
                    if sid:
                        lead_row = db.execute(text(
                            "SELECT id FROM leads WHERE organization_id = :oid AND sid = :sid"
                        ), {"oid": _db_ctx["org_id"], "sid": sid}).fetchone()
                        if lead_row:
                            lead_id = lead_row[0]

                    # Insert booking for a 30-min discovery call
                    result = db.execute(text("""
                        INSERT INTO bookings (organization_id, lead_id, service_id, service_name,
                            duration_min, price_eur, booking_date, booking_time,
                            customer_name, customer_phone, customer_email, status)
                        VALUES (:oid, :lid, :sid, :sname, :dur, :price, :bdate, :btime,
                            :cname, :cphone, :cemail, 'confirmed')
                        RETURNING id
                    """), {
                        "oid": _db_ctx["org_id"], "lid": lead_id,
                        "sid": "discovery-call", "sname": "Discovery Call",
                        "dur": 30, "price": 0,
                        "bdate": datum, "btime": ura, "cname": ime,
                        "cphone": _db_ctx.get("lead_phone"),
                        "cemail": _db_ctx.get("lead_email"),
                    })
                    booking_id = result.scalar()

                    # Publish event
                    db.execute(text("""
                        INSERT INTO lead_events (organization_id, sid, event_type, payload_json)
                        VALUES (:oid, :sid, :etype, :payload)
                    """), {
                        "oid": _db_ctx["org_id"], "sid": _db_ctx.get("sid", "*"),
                        "etype": "booking.created",
                        "payload": json.dumps({
                            "id": booking_id, "bookingDate": datum, "bookingTime": ura,
                            "serviceName": "Discovery Call", "customerName": ime,
                            "durationMin": 30, "priceEur": 0,
                        }),
                    })
                    db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist discovery call: {e}")

            return json.dumps({
                "potrjeno": True,
                "id": booking_id,
                "storitev": "Discovery Call",
                "trajanje_min": 30,
                "datum": datum, "ura": ura,
                "sporocilo": f"Discovery call scheduled for {datum} at {ura}. A team member will reach out then. Looking forward to it!"
            }, ensure_ascii=False)

        if name == "ace_request_team":
            razlog = args.get("razlog", "")
            if not _is_open():
                return json.dumps({
                    "uspesno": False,
                    "sporocilo": "Currently closed (Mon-Fri 9-17). Offer to schedule a call for the next working day using ace_schedule_call instead, or ask for contact info.",
                    "naslednji_delovni_dan": _next_working_day(),
                }, ensure_ascii=False)
            return json.dumps({
                "uspesno": True,
                "sporocilo": "Team requested. Someone will join the conversation shortly.",
            }, ensure_ascii=False)

        if name == "ace_update_profile":
            # Return the captured fields — graph will merge them into state
            captured = {}
            for field in ["use_case", "company_type", "scale", "current_system", "timeline", "business_name", "budget", "problem"]:
                val = args.get(field, "")
                if val:
                    captured[field] = val
            return json.dumps({
                "posodobljeno": True,
                "zajeto": captured,
                "sporocilo": f"Profile updated: {', '.join(captured.keys())}",
            }, ensure_ascii=False)

        return json.dumps({"napaka": f"Unknown tool: {name}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return json.dumps({"napaka": str(e)[:300]}, ensure_ascii=False)
