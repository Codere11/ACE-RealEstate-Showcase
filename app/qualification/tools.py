"""Salon receptionist tools — appointment booking, availability, services."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("ace.tools")

# ── Salon data (would come from DB in production) ──

SERVICES = [
    {
        "id": "nega-obraza",
        "name": "Nega obraza",
        "duration_min": 45,
        "price_eur": 35,
        "description": "Globinsko čiščenje, vlaženje in masaža obraza. Idealno za vse tipe kože.",
    },
    {
        "id": "maska-obraza",
        "name": "Maska obraza",
        "duration_min": 30,
        "price_eur": 25,
        "description": "Hitra osvežitev z vrhunsko masko po izboru. Super pred dogodkom.",
    },
    {
        "id": "ciscenje-obraza",
        "name": "Čiščenje obraza",
        "duration_min": 60,
        "price_eur": 50,
        "description": "Temeljito ročno čiščenje, piling in pomirjevalna maska. Naš najbolj priljubljen tretma.",
    },
]

OPEN_HOUR = 9
CLOSE_HOUR = 18

# Simulated bookings store (in-memory for prototype)
_bookings: dict = {}  # key = "YYYY-MM-DD HH:MM" -> booked service id


def _is_open() -> bool:
    now = datetime.now()
    return OPEN_HOUR <= now.hour < CLOSE_HOUR and now.weekday() < 5  # Mon-Fri


def _status_text() -> str:
    if _is_open():
        return f"ODPRTO (do {CLOSE_HOUR}:00)"
    return f"ZAPRTO (odprti pon–pet {OPEN_HOUR}:00–{CLOSE_HOUR}:00)"


def _next_working_day() -> str:
    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:  # skip weekends
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _free_slots(date_str: str, service_duration_min: int = 45) -> list[dict]:
    """Generate available time slots for a given date."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []

    if date.weekday() >= 5:  # weekend
        return []

    slots = []
    for h in range(OPEN_HOUR, CLOSE_HOUR):
        for m in range(0, 60, service_duration_min):
            time_key = f"{date_str} {h:02d}:{m:02d}"
            if time_key not in _bookings:
                slots.append({
                    "time": f"{h:02d}:{m:02d}",
                    "available": True,
                })

    # Mark lunch break (12:00–12:45) as unavailable
    slots = [s for s in slots if s["time"] != "12:00"]

    return slots


# ── Tools the LLM can call ──

SALON_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "salon_get_context",
            "description": "Pridobi trenutno stanje salona: ali je odprt/zaprt, današnji prosti termini, delovni čas.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "salon_get_services",
            "description": "Pridobi seznam vseh kozmetičnih storitev s cenami, trajanjem in opisi.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "salon_check_availability",
            "description": "Preveri proste termine za določen datum. Vrne seznam razpoložljivih ur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datum": {
                        "type": "string",
                        "description": "Datum v formatu YYYY-MM-DD, npr. '2026-05-24'",
                    },
                },
                "required": ["datum"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "salon_book_appointment",
            "description": "Rezerviraj termin za določeno storitev, datum in uro. Vrni potrditev rezervacije.",
            "parameters": {
                "type": "object",
                "properties": {
                    "storitev_id": {
                        "type": "string",
                        "description": "ID storitve: 'nega-obraza', 'maska-obraza' ali 'ciscenje-obraza'",
                        "enum": ["nega-obraza", "maska-obraza", "ciscenje-obraza"],
                    },
                    "datum": {
                        "type": "string",
                        "description": "Datum v formatu YYYY-MM-DD",
                    },
                    "ura": {
                        "type": "string",
                        "description": "Ura v formatu HH:MM, npr. '09:00'",
                    },
                },
                "required": ["storitev_id", "datum", "ura"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "salon_request_staff",
            "description": "Zahtevaj povezavo s človeškim osebjem (kozmetičarko). Uporabi, ko stranka izrecno želi govoriti z osebo ali ko je vprašanje preveč specifično.",
            "parameters": {
                "type": "object",
                "properties": {
                    "razlog": {
                        "type": "string",
                        "description": "Kratek razlog za zahtevo po osebju",
                    },
                },
                "required": ["razlog"],
            },
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """Execute salon receptionist tool — deterministic, no LLM URL construction."""
    try:
        if name == "salon_get_context":
            today = datetime.now().strftime("%Y-%m-%d")
            free = _free_slots(today, 45)
            return json.dumps(
                {
                    "status": _status_text(),
                    "odprto": _is_open(),
                    "delovni_cas": f"pon–pet {OPEN_HOUR}:00–{CLOSE_HOUR}:00, sobota po dogovoru, nedelja zaprto",
                    "danes": today,
                    "prosti_termini_danes": len(free),
                    "naslednji_delovni_dan": _next_working_day(),
                },
                ensure_ascii=False,
            )

        if name == "salon_get_services":
            return json.dumps({"storitve": SERVICES}, ensure_ascii=False)

        if name == "salon_check_availability":
            date_str = args.get("datum", "")
            if not date_str:
                date_str = _next_working_day()

            slots_45 = _free_slots(date_str, 45)
            slots_30 = _free_slots(date_str, 30)
            slots_60 = _free_slots(date_str, 60)

            return json.dumps(
                {
                    "datum": date_str,
                    "termini_za_45min": slots_45[:8],
                    "termini_za_30min": slots_30[:10],
                    "termini_za_60min": slots_60[:6],
                    "skupaj_prostih": len(slots_45),
                },
                ensure_ascii=False,
            )

        if name == "salon_book_appointment":
            storitev_id = args.get("storitev_id", "")
            datum = args.get("datum", "")
            ura = args.get("ura", "")

            service = next((s for s in SERVICES if s["id"] == storitev_id), None)
            if not service:
                return json.dumps(
                    {"napaka": f"Neznana storitev: {storitev_id}. Na voljo: nega-obraza, maska-obraza, ciscenje-obraza"},
                    ensure_ascii=False,
                )

            time_key = f"{datum} {ura}"
            if time_key in _bookings:
                return json.dumps(
                    {"napaka": f"Termin {datum} ob {ura} je žal že zaseden. Izberite drug termin."},
                    ensure_ascii=False,
                )

            # Validate slot is free
            slots = _free_slots(datum, service["duration_min"])
            if not any(s["time"] == ura for s in slots):
                return json.dumps(
                    {"napaka": f"Termin {datum} ob {ura} ni na voljo. Prosti termini: {[s['time'] for s in slots[:5]]}"},
                    ensure_ascii=False,
                )

            # Book it
            _bookings[time_key] = storitev_id

            return json.dumps(
                {
                    "potrjeno": True,
                    "storitev": service["name"],
                    "trajanje_min": service["duration_min"],
                    "cena_eur": service["price_eur"],
                    "datum": datum,
                    "ura": ura,
                    "sporocilo": f"Vaš termin je potrjen! {service['name']} v {service['duration_min']} min, {service['price_eur']} €. Lepo vabljeni! 💆‍♀️",
                },
                ensure_ascii=False,
            )

        if name == "salon_request_staff":
            if not _is_open():
                return json.dumps(
                    {
                        "uspesno": False,
                        "sporocilo": "Salon je trenutno zaprt. Osebje bo na voljo naslednji delovni dan. Vam lahko medtem pomagam z rezervacijo?",
                        "naslednji_delovni_dan": _next_working_day(),
                    },
                    ensure_ascii=False,
                )

            return json.dumps(
                {
                    "uspesno": True,
                    "sporocilo": "Zahteva za osebje poslana. Maja (kozmeticarka) bo z vami v nekaj trenutkih.",
                    "osebje": "Maja",
                    "vloga": "Kozmeticarka",
                },
                ensure_ascii=False,
            )

        return json.dumps({"napaka": f"Neznano orodje: {name}"}, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return json.dumps({"napaka": str(e)[:300]}, ensure_ascii=False)
