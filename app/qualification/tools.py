"""Salon receptionist tools — appointment booking, availability, services."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger("ace.tools")

# ── Salon data ──

SERVICES = [
    {"id": "nega-obraza", "name": "Nega obraza", "duration_min": 45, "price_eur": 35,
     "description": "Globinsko čiščenje, vlaženje in masaža obraza. Idealno za vse tipe kože."},
    {"id": "maska-obraza", "name": "Maska obraza", "duration_min": 30, "price_eur": 25,
     "description": "Hitra osvežitev z vrhunsko masko po izboru. Super pred dogodkom."},
    {"id": "ciscenje-obraza", "name": "Čiščenje obraza", "duration_min": 60, "price_eur": 50,
     "description": "Temeljito ročno čiščenje, piling in pomirjevalna maska. Naš najbolj priljubljen tretma."},
]

OPEN_HOUR = 9
CLOSE_HOUR = 18

# ── DB context (set by backend before graph runs) ──
_db_ctx: Optional[dict] = None  # {"org_id": int, "sid": str, "lead_phone": str|None, "lead_email": str|None}

def set_db_context(org_id: int, sid: str, lead_phone: Optional[str] = None, lead_email: Optional[str] = None):
    global _db_ctx
    _db_ctx = {"org_id": org_id, "sid": sid, "lead_phone": lead_phone, "lead_email": lead_email}

def _is_open() -> bool:
    now = datetime.now()
    return OPEN_HOUR <= now.hour < CLOSE_HOUR and now.weekday() < 5

def _status_text() -> str:
    return f"ODPRTO (do {CLOSE_HOUR}:00)" if _is_open() else f"ZAPRTO (odprti pon–pet {OPEN_HOUR}:00–{CLOSE_HOUR}:00)"

def _next_working_day() -> str:
    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")

def _get_booked_slots(date_str: str) -> set:
    """Query real bookings table for taken slots on a date. Uses sync engine."""
    if not _db_ctx:
        return set()
    try:
        from app.core.db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            result = db.execute(
                text("SELECT booking_time, duration_min FROM bookings WHERE organization_id = :oid AND booking_date = :d AND status != 'cancelled'"),
                {"oid": _db_ctx["org_id"], "d": date_str}
            )
            return {(row[0], row[1]) for row in result.all()}
    except Exception as e:
        logger.warning(f"Failed to query bookings: {e}")
        return set()

def _slot_overlaps(slot_time: str, slot_duration: int, bookings: set) -> bool:
    """Check if a proposed slot [time, time+duration) overlaps any existing booking."""
    slot_h, slot_m = map(int, slot_time.split(":"))
    slot_start = slot_h * 60 + slot_m
    slot_end = slot_start + slot_duration
    for bk_time, bk_dur in bookings:
        bh, bm = map(int, bk_time.split(":"))
        bk_start = bh * 60 + bm
        bk_end = bk_start + bk_dur
        if slot_start < bk_end and slot_end > bk_start:
            return True
    return False

def _free_slots_from_bookings(date_str: str, service_duration_min: int, bookings: set) -> list[dict]:
    """Like _free_slots but uses an already-queried bookings set (under lock)."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []
    if date.weekday() >= 5:
        return []
    slots = []
    for h in range(OPEN_HOUR, CLOSE_HOUR):
        for m in range(0, 60, service_duration_min):
            t = f"{h:02d}:{m:02d}"
            if t != "12:00" and not _slot_overlaps(t, service_duration_min, bookings):
                slots.append({"time": t, "available": True})
    return slots

def _free_slots(date_str: str, service_duration_min: int = 45) -> list[dict]:
    """Generate available time slots for a given date."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []
    if date.weekday() >= 5:
        return []
    bookings = _get_booked_slots(date_str)
    slots = []
    for h in range(OPEN_HOUR, CLOSE_HOUR):
        for m in range(0, 60, service_duration_min):
            t = f"{h:02d}:{m:02d}"
            if t != "12:00" and not _slot_overlaps(t, service_duration_min, bookings):
                slots.append({"time": t, "available": True})
    return slots

# ── Tools the LLM can call ──

SALON_TOOLS = [
    {"type": "function", "function": {
        "name": "salon_get_context",
        "description": "Pridobi trenutno stanje salona: ali je odprt/zaprt, delovni čas, naslednji delovni dan.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "salon_get_services",
        "description": "Pridobi seznam vseh kozmetičnih storitev s cenami, trajanjem in opisi.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "salon_check_availability",
        "description": "Preveri resnično proste termine za določen datum iz baze rezervacij. Vrne samo dejansko proste termine.",
        "parameters": {"type": "object", "properties": {
            "datum": {"type": "string", "description": "Datum v formatu YYYY-MM-DD, npr. '2026-05-24'. Če ni podan, se uporabi naslednji delovni dan."},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "salon_check_contact",
        "description": "Preveri ali imamo kontaktne podatke stranke (telefon ali email). Če NE, NE smeš rezervirati — najprej vljudno prosi za kontakt (telefon ali email).",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "salon_book_appointment",
        "description": "Rezerviraj termin. PRED tem MORAŠ poklicati salon_check_contact in dobiti ok:true. Če kontakt manjka, najprej prosi zanj.",
        "parameters": {"type": "object", "properties": {
            "storitev_id": {"type": "string", "enum": ["nega-obraza", "maska-obraza", "ciscenje-obraza"]},
            "datum": {"type": "string", "description": "Datum v formatu YYYY-MM-DD"},
            "ura": {"type": "string", "description": "Ura v formatu HH:MM, npr. '09:00'"},
            "ime_stranke": {"type": "string", "description": "Ime stranke (iz pogovora ali 'Stranka' če ne vemo)"},
        }, "required": ["storitev_id", "datum", "ura"]},
    }},
    {"type": "function", "function": {
        "name": "salon_request_staff",
        "description": "Zahtevaj povezavo s človeškim osebjem.",
        "parameters": {"type": "object", "properties": {
            "razlog": {"type": "string", "description": "Kratek razlog za zahtevo po osebju"},
        }, "required": ["razlog"]},
    }},
]

def execute_tool(name: str, args: dict) -> str:
    try:
        if name == "salon_get_context":
            today = datetime.now().strftime("%Y-%m-%d")
            free = _free_slots(today, 45)
            return json.dumps({
                "status": _status_text(), "odprto": _is_open(),
                "delovni_cas": f"pon–pet {OPEN_HOUR}:00–{CLOSE_HOUR}:00, sobota po dogovoru, nedelja zaprto",
                "danes": today, "prosti_termini_danes": len(free),
                "naslednji_delovni_dan": _next_working_day(),
            }, ensure_ascii=False)

        if name == "salon_get_services":
            return json.dumps({"storitve": SERVICES}, ensure_ascii=False)

        if name == "salon_check_contact":
            if not _db_ctx:
                return json.dumps({"ok": True, "sporocilo": "Kontaktna validacija ni na voljo — nadaljuj."}, ensure_ascii=False)
            has_contact = bool(_db_ctx.get("lead_phone") or _db_ctx.get("lead_email"))
            if has_contact:
                return json.dumps({"ok": True, "ima_kontakt": True, "sporocilo": "Stranka ima kontaktne podatke."}, ensure_ascii=False)
            return json.dumps({"ok": False, "ima_kontakt": False, "sporocilo": "STRANKA NIMA KONTAKTA. Vljudno prosi za telefonsko številko ali email, preden rezerviraš termin."}, ensure_ascii=False)

        if name == "salon_check_availability":
            date_str = args.get("datum") or _next_working_day()
            slots_45 = _free_slots(date_str, 45)
            slots_30 = _free_slots(date_str, 30)
            slots_60 = _free_slots(date_str, 60)
            return json.dumps({
                "datum": date_str,
                "termini_za_45min": slots_45[:8],
                "termini_za_30min": slots_30[:10],
                "termini_za_60min": slots_60[:6],
                "skupaj_prostih": len(slots_45),
            }, ensure_ascii=False)

        if name == "salon_book_appointment":
            storitev_id = args.get("storitev_id", "")
            datum = args.get("datum", "")
            ura = args.get("ura", "")
            ime = args.get("ime_stranke", "Stranka")

            service = next((s for s in SERVICES if s["id"] == storitev_id), None)
            if not service:
                return json.dumps({"napaka": f"Neznana storitev: {storitev_id}"}, ensure_ascii=False)

            # Check slot is free (overlap-aware, not just exact match)
            # ── ALL of this must happen in ONE transaction with FOR UPDATE lock ──
            booking_id = None
            if _db_ctx:
                try:
                    from app.core.db import SessionLocal
                    from sqlalchemy import text
                    with SessionLocal() as db:
                        # Lock all bookings for this org+date to prevent race-condition double-booking
                        rows = db.execute(text(
                            "SELECT booking_time, duration_min FROM bookings WHERE organization_id = :oid AND booking_date = :d AND status != 'cancelled' FOR UPDATE"
                        ), {"oid": _db_ctx["org_id"], "d": datum}).all()
                        bookings = {(r[0], r[1]) for r in rows}

                        # Check overlap (under lock)
                        if _slot_overlaps(ura, service["duration_min"], bookings):
                            free = [s["time"] for s in _free_slots_from_bookings(datum, service["duration_min"], bookings)[:6]]
                            db.rollback()
                            return json.dumps({"napaka": f"Termin {datum} ob {ura} je žal že zaseden. Prosti termini: {free}"}, ensure_ascii=False)

                        # Validate slot exists in schedule
                        slots = _free_slots_from_bookings(datum, service["duration_min"], bookings)
                        if not any(s["time"] == ura for s in slots):
                            free = [s["time"] for s in slots[:5]]
                            db.rollback()
                            return json.dumps({"napaka": f"Termin {datum} ob {ura} ni na voljo. Prosti termini: {free}"}, ensure_ascii=False)

                        # Insert booking (under same lock)
                        result = db.execute(text("""
                            INSERT INTO bookings (organization_id, service_id, service_name, duration_min, price_eur,
                                booking_date, booking_time, customer_name, customer_phone, customer_email, status)
                            VALUES (:oid, :sid, :sname, :dur, :price, :bdate, :btime, :cname, :cphone, :cemail, 'confirmed')
                            RETURNING id
                        """), {
                            "oid": _db_ctx["org_id"], "sid": service["id"], "sname": service["name"],
                            "dur": service["duration_min"], "price": service["price_eur"],
                            "bdate": datum, "btime": ura, "cname": ime,
                            "cphone": _db_ctx.get("lead_phone"), "cemail": _db_ctx.get("lead_email"),
                        })
                        booking_id = result.scalar()
                        # Also persist event so dashboard picks it up
                        db.execute(text("""
                            INSERT INTO lead_events (organization_id, sid, event_type, payload_json)
                            VALUES (:oid, :sid, :etype, :payload)
                        """), {
                            "oid": _db_ctx["org_id"], "sid": _db_ctx.get("sid", "*"),
                            "etype": "booking.created",
                            "payload": json.dumps({
                                "id": booking_id, "bookingDate": datum, "bookingTime": ura,
                                "serviceName": service["name"], "customerName": ime,
                                "durationMin": service["duration_min"], "priceEur": service["price_eur"],
                            }),
                        })
                        db.commit()
                except Exception as e:
                    logger.warning(f"Failed to persist booking: {e}")

            return json.dumps({
                "potrjeno": True,
                "storitev": service["name"], "trajanje_min": service["duration_min"],
                "cena_eur": service["price_eur"], "datum": datum, "ura": ura,
                "sporocilo": f"Vaš termin je potrjen! {service['name']} v {service['duration_min']} min, {service['price_eur']} €. Lepo vabljeni! 💆‍♀️",
            }, ensure_ascii=False)

        if name == "salon_request_staff":
            if not _is_open():
                return json.dumps({
                    "uspesno": False,
                    "sporocilo": "Salon je trenutno zaprt. Osebje bo na voljo naslednji delovni dan.",
                    "naslednji_delovni_dan": _next_working_day(),
                }, ensure_ascii=False)
            return json.dumps({
                "uspesno": True,
                "sporocilo": "Zahteva za osebje poslana. Maja (kozmeticarka) bo z vami v nekaj trenutkih.",
            }, ensure_ascii=False)

        return json.dumps({"napaka": f"Neznano orodje: {name}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return json.dumps({"napaka": str(e)[:300]}, ensure_ascii=False)
