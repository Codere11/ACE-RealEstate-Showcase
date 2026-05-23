from __future__ import annotations

import json
from typing import Any, Dict, List


def _prune(value: Any) -> Any:
    if isinstance(value, dict):
        out = {k: _prune(v) for k, v in value.items() if v not in (None, "", [], {})}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        out = [_prune(v) for v in value if v not in (None, "", [], {})]
        return [v for v in out if v not in (None, "", [], {})]
    return value


# ── Core identity — always in system prompt ──

IDENTITY = (
    "Ti si AI Receptor za kozmetični salon Lepota & Sprostitev. "
    "Si prijazen, topel, profesionalen — kot izkušen receptor. "
    "Govoriš naravno slovenščino, kratko in jedrnato."
)


# ── Per-node prompts — each has exactly ONE job ──

CLASSIFY_PROMPT = """Glede na zadnje sporočilo stranke in zgodovino pogovora, določi kaj stranka želi ZDAJ.

Vrni JSON:
{
  "stage": "greeting|discovery|availability|booking|handoff|idle"
}

Pravila:
- "greeting": prvi stik, stranka se prvič oglaša ali pozdravlja na začetku pogovora
- "discovery": stranka sprašuje o storitvah, cenah, primerjavah, išče informacije
- "availability": stranka želi rezervirati, sprašuje o terminih
- "booking": stranka je izbrala točen termin — potrdi
- "handoff": stranka želi govoriti z osebjem (človekom)
- "idle": stranka samo klepeta, se zahvaljuje, pozdravlja sredi pogovora — ne potrebuje ničesar konkretnega
"""


GREETING_WITH_HOURS = """Prvič pozdravljaš stranko. Povej:
1. Topel pozdrav
2. Ali je salon odprt ali zaprt (en stavek)
3. Na kratko omeni da imate 3 storitve (ne naštevaj vseh — samo "imamo nego, masko in čiščenje obraza")
4. Vprašaj kako lahko pomagaš

Bodi topel, kratek — max 4 stavke."""


GREETING_WITHOUT_HOURS = """Stranka se je vrnila v pogovor. Toplo pozdravi in vprašaj kako lahko pomagaš.
Bodi kratek — 1-2 stavki."""


DISCOVERY_PROMPT = """Stranka sprašuje o storitvah ali išče informacije.
Odgovori na njeno vprašanje direktno in informativno.
Če sprašuje o določeni storitvi — opiši jo podrobno.
Če primerja — primerjaj.
Če sprašuje na splošno — opiši kar jo zanima, ne naštevaj vseh treh.
Bodi koristen, ne vsiljiv. 2-4 stavke."""


AVAILABILITY_PROMPT = """Stranka želi rezervirati termin.
Povej katere termine imaš na voljo (iz orodja).
Vprašaj kateri čas ji ustreza.
Bodi konkreten in veder. 2-3 stavke + seznam terminov."""


BOOKING_PROMPT = """Stranka je izbrala termin. Potrdi rezervacijo.
Povej: storitev, datum, uro, ceno.
Zahvali se in povej da so veseli njenega obiska.
Toplo, kratko — 2-3 stavke."""


HANDOFF_PROMPT = """Stranka želi govoriti z osebjem.
Povej da boš povezal/a z osebjem.
Če je salon zaprt — povej da osebje trenutno ni na voljo in ponudi rezervacijo za naslednji delovni dan.
Bodi razumevajoč. 1-2 stavki."""


IDLE_PROMPT = """Stranka samo klepeta ali se zahvaljuje.
Bodi topel in kratek. 1 stavek.
Ne ponujaj ničesar — samo bodi prijazen."""


# ── Prompt builders ──

def build_classify_prompt(latest_message: str, recent_messages: List[Dict[str, str]]) -> str:
    history = json.dumps(
        [{"r": m.get("role", "user"), "t": m.get("text", "")} for m in (recent_messages or [])[-4:]],
        ensure_ascii=False,
    )
    return (
        f"{IDENTITY}\n\n"
        f"{CLASSIFY_PROMPT}\n\n"
        f"ZGODOVINA: {history}\n"
        f"ZADNJE SPOROČILO: {json.dumps(latest_message, ensure_ascii=False)}\n"
    )


def build_node_prompt(
    node_type: str,
    *,
    hours_mentioned: bool,
    services_presented: bool,
    state_json: str,
    messages_json: str,
    latest_json: str,
) -> str:
    """Build a focused prompt for a specific graph node."""
    if node_type == "greeting":
        task = GREETING_WITH_HOURS if not hours_mentioned else GREETING_WITHOUT_HOURS
    elif node_type == "discovery":
        task = DISCOVERY_PROMPT
    elif node_type == "availability":
        task = AVAILABILITY_PROMPT
    elif node_type == "booking":
        task = BOOKING_PROMPT
    elif node_type == "handoff":
        task = HANDOFF_PROMPT
    else:
        task = IDLE_PROMPT

    return (
        f"{IDENTITY}\n\n"
        f"{task}\n\n"
        f"TRENUTNO STANJE SALONA: {state_json}\n"
        f"ZGODOVINA: {messages_json}\n"
        f"STRANKA: {latest_json}\n\n"
        f"Vrni SAMO JSON: {{\"rep\":\"tvoj odgovor\"}}"
    )
