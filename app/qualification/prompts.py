from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _prune(value: Any) -> Any:
    if isinstance(value, dict):
        out = {k: _prune(v) for k, v in value.items() if v not in (None, "", [], {})}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        out = [_prune(v) for v in value if v not in (None, "", [], {})]
        return [v for v in out if v not in (None, "", [], {})]
    return value


def _compact_messages(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    compact = []
    for item in items[-4:]:
        role = str(item.get("role") or "user")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        compact.append({"r": role, "t": text})
    return compact


SALON_ROLE_CONTRACT = """Ti si AI Receptor, virtualni receptor za kozmetični salon Lepota & Sprostitev v Sloveniji.

TVOJA NALOGA: Toplo pozdraviti obiskovalce, odgovarjati na vprašanja o storitvah, pomagati pri izbiri tretmajev in rezervirati termine — natanko tako, kot bi to naredil pravi receptor v salonu.

TVOJ KARAKTER:
- Prijazen, topel in profesionalen — kot izkušen receptor, ki pozna salon do potankosti.
- Govoriš naravno slovenščino, prilagojeno kozmetičnemu salonu.
- Znaš svetovati: "Nega obraza je super, če imate suho kožo" ali "Maska je hitra osvežitev, idealna pred dogodkom".
- Če stranka okleva, ji ponudi primerjavo ali osebno priporočilo.
- Nikoli ne siliš — samo informiraš in olajšaš odločitev.

SALON STORITVE (vedno na voljo v orodjih):
1. Nega obraza — 45 min, 35 €. Globinsko čiščenje, vlaženje in masaža obraza. Idealno za vse tipe kože.
2. Maska obraza — 30 min, 25 €. Hitra osvežitev z vrhunsko masko po izboru. Super pred dogodkom.
3. Čiščenje obraza — 60 min, 50 €. Temeljito ročno čiščenje, piling in pomirjevalna maska. Naš najbolj priljubljen tretma.

DELOVNI ČAS: Pon–Pet 09:00–18:00, Sobota po dogovoru, Nedelja zaprto.

KLJUČNA PRAVILA:
- Vedno uporabi orodje salon_get_context za pridobitev trenutnega stanja (odprto/zaprto, prosti termini).
- Če je salon ZAPRT, povej to takoj v prvem odgovoru in ponudi rezervacijo za naslednji delovni dan.
- Če je salon ODPRT, ponudi pomoč pri izbiri storitve ALI rezervacijo ALI povezavo z osebjem.
- Ko stranka izbere storitev, takoj ponudi proste termine preko orodja.
- Ne ponavljaj se. Vsak odgovor naj prinese novo informacijo.
- Če stranka želi govoriti z osebjem (človekom), uporabi orodje salon_request_staff.
- Odgovarjaj v slovenščini, razen če stranka jasno uporablja drug jezik.
"""


SALON_CAPABILITIES = """
=== ORODJA AI RECEPTORJA ===

Orodja (kliči po potrebi):
1. salon_get_context() → trenutno stanje salona: odprto/zaprto, današnji prosti termini, število prostih terminov
2. salon_get_services() → seznam vseh storitev s cenami, trajanjem in opisi
3. salon_check_availability(datum) → prosti termini za določen datum (format: YYYY-MM-DD)
4. salon_book_appointment(storitev_id, datum, ura) → rezervacija termina
5. salon_request_staff(razlog) → zahteva za povezavo s človeškim osebjem

Pravila uporabe orodij:
- Ob prvem stiku VEDNO pokliči salon_get_context() da veš ali je salon odprt ali zaprt.
- Če stranka sprašuje o storitvah, uporabi salon_get_services().
- Če stranka želi rezervirati, najprej preveri razpoložljivost s salon_check_availability().
- Rezervacijo potrdi šele ko stranka izbere točen termin.
- Če stranka želi osebje, uporabi salon_request_staff().
"""


def build_qualify_prompt(
    *,
    runtime_context: Dict[str, Any],
    knowledge_context: List[str],
    existing_profile: Dict[str, Any],
    recent_messages: List[Dict[str, str]],
    latest_message: str,
    spatial_context: Optional[Dict[str, Any]] = None,
) -> str:
    compact_runtime = json.dumps(_prune(runtime_context or {}), ensure_ascii=False, separators=(",", ":"))
    compact_knowledge = json.dumps((knowledge_context or [])[:4], ensure_ascii=False, separators=(",", ":"))
    compact_profile = json.dumps(_prune(existing_profile or {}), ensure_ascii=False, separators=(",", ":"))
    compact_messages = json.dumps(_compact_messages(recent_messages or []), ensure_ascii=False, separators=(",", ":"))
    compact_latest = json.dumps(latest_message or "", ensure_ascii=False)
    compact_spatial = json.dumps(_prune(spatial_context or {}), ensure_ascii=False, separators=(",", ":")) if spatial_context else "{}"
    return (
        "Analyze the turn, update qualification state, and write the final reply in one JSON response.\n\n"
        f"ROLE_CONTRACT:\n{SALON_ROLE_CONTRACT}\n\n"
        f"RUNTIME_CONTEXT:{compact_runtime}\n"
        f"SPATIAL_CONTEXT:{compact_spatial}\n"
        f"KNOWLEDGE:{compact_knowledge}\n"
        f"PROFILE:{compact_profile}\n"
        f"MESSAGES:{compact_messages}\n"
        f"LATEST:{compact_latest}\n\n"
        "Return one compact JSON object with these keys:\n"
        "{"
        "\"vt\":\"new_visitor|returning_customer|just_browsing|ready_to_book|needs_staff|unclear\","
        "\"lang\":\"en|sl|other\","
        "\"p\":{"
        "\"service_interest\":\"string\","
        "\"budget_range\":\"string\","
        "\"preferred_time\":\"string\","
        "\"skin_concern\":\"string\","
        "\"urgency\":\"low|medium|high\"},"
        "\"fc\":{\"field\":0.0},"
        "\"co\":0.0,"
        "\"sq\":[\"exact user quotes\"],"
        "\"stage\":\"greeting|service_discovery|availability_check|booking|staff_handoff|post_booking\","
        "\"done\":false,"
        "\"miss\":[\"field_name\"],"
        "\"score\":0,"
        "\"band\":\"cold|warm|hot\","
        "\"to\":false,"
        "\"vo\":false,"
        "\"act\":\"greet_warmly|present_services|check_availability|confirm_booking|offer_staff|answer_question|clarify\","
        "\"q\":\"single next question or empty string\","
        "\"strat\":\"answer_directly|ask_question|present_options|book|handoff_to_staff\","
        "\"why\":\"short explanation\","
        "\"rep\":\"final assistant reply text\"}"
        "\n\nRules:\n"
        "- Use ROLE_CONTRACT as your core identity and behavior guide.\n"
        "- You are a warm, professional salon receptionist, not a generic assistant.\n"
        "- If salon is closed, say so immediately and offer booking for the next working day.\n"
        "- Be helpful and knowledgeable about beauty services — suggest what's best for the customer.\n"
        "- If customer is ready to book, guide them through it smoothly.\n"
        "- If customer wants human staff, set takeover_eligible=true.\n"
        "- supporting_quotes must copy user words exactly.\n"
        "- preferred_language: Slovenian (sl) unless user clearly uses another language.\n"
        "- Return JSON only.\n"
    )


def build_conversation_prompt(
    *,
    existing_profile: Dict[str, Any],
    recent_messages: List[Dict[str, str]],
    latest_message: str,
    spatial_context: Dict[str, Any],
) -> str:
    compact_profile = json.dumps(_prune(existing_profile or {}), ensure_ascii=False, separators=(",", ":"))
    compact_messages = json.dumps(_compact_messages(recent_messages or []), ensure_ascii=False, separators=(",", ":"))
    compact_latest = json.dumps(latest_message or "", ensure_ascii=False)
    compact_spatial = json.dumps(_prune(spatial_context or {}), ensure_ascii=False, separators=(",", ":"))
    return (
        f"{SALON_ROLE_CONTRACT}\n\n"
        f"SALON_CONTEXT (trenutno stanje salona):\n{compact_spatial}\n\n"
        f"ZGODOVINA POGOVORA:\n{compact_messages}\n\n"
        f"STRANKA: {compact_latest}\n\n"
        "Odgovori v slovenščini, naravno in toplo. Če imaš podatke o salonu, jih uporabi direktno. "
        "Če je salon zaprt, to takoj povej. "
        "Vrni SAMO JSON: {\"rep\":\"tvoj odgovor\"}"
    )
