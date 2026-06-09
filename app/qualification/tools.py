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
        "description": "Schedule a discovery call with the ACE team. PREREQUISITE: must have contact info (ace_check_contact must return ok:true). The call duration is always 30 minutes.",
        "parameters": {"type": "object", "properties": {
            "datum": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            "ura": {"type": "string", "description": "Time in HH:MM format, e.g. '10:00'"},
            "ime": {"type": "string", "description": "Visitor name from conversation"},
        }, "required": ["datum", "ura", "ime"]},
    }},
    {"type": "function", "function": {
        "name": "ace_request_team",
        "description": "Request a human team member to join the conversation. Use when the visitor has a complex question or explicitly asks to speak to a person.",
        "parameters": {"type": "object", "properties": {
            "razlog": {"type": "string", "description": "Brief reason for the request"},
        }, "required": ["razlog"]},
    }},
]


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
            datum = args.get("datum", "")
            ura = args.get("ura", "")
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
                    "sporocilo": "We are currently closed. The team will be available the next working day.",
                    "naslednji_delovni_dan": _next_working_day(),
                }, ensure_ascii=False)
            return json.dumps({
                "uspesno": True,
                "sporocilo": "Team requested. Someone will join the conversation shortly.",
            }, ensure_ascii=False)

        return json.dumps({"napaka": f"Unknown tool: {name}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return json.dumps({"napaka": str(e)[:300]}, ensure_ascii=False)
