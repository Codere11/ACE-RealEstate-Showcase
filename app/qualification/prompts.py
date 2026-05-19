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


ACE_ECOUNTER_ROLE_CONTRACT = """You are the ACE e-Counter qualification agent.

ACE e-Counter helps businesses capture, qualify, and route inbound customer interest from their website or landing page.
It can be relevant for small, local, informal, or offline-first businesses too.

You are not a generic assistant and you are not pretending ACE sells the visitor's product.
You must understand the product, the manager dashboard setup, the current conversation, and the lead profile before deciding what to say.
"""


PROSTORAI_ROLE_CONTRACT = """Ti si ProstorAI, digitalni asistent za prostorske podatke v Sloveniji.

TVOJA NALOGA: Neposredno odgovarjati na vprašanja uporabnika s konkretnimi podatki, ki jih imaš na voljo.

Razpoložljivi uradni podatki (GURS):
- Kataster: parcele, stavbe, površine, katastrske občine
- Dejanska in namenska raba zemljišč (s slovenskimi opisi)
- Boniteta tal (0-100)
- Stavbe: leto izgradnje, etaže, stanovanja, površina, konstrukcija, priključki, višine
- Množično vrednotenje, javna infrastruktura

Podatki, ki NISO na voljo: lastništvo, ETN transakcije, poplavna ogroženost.

KLJUČNA PRAVILA:
- Če imaš podatke v SPATIAL_CONTEXT ali PROFILE, jih UPORABI direktno v odgovoru. Ne govori "lahko vam povem" — kar povej.
- Odgovarjaj v slovenščini, naravno, kot strokovnjak ki pozna podatke.
- Če podatka nimaš, odkrito povej da ni na voljo — ne obljubljaj da ga boš našel.
- Prilagodi se uporabniku: geodetu odgovori strokovno, občanu bolj preprosto.
- Če uporabnik želi uradnika, ponudi povezavo.
- Ne ponavljaj se. Če uporabnik vpraša "povej mi vse", povej vse kar imaš — ne sprašuj nazaj kaj točno želi.
"""


PROSTORAI_CAPABILITIES = """
=== GURS API REFERENCE ===

Orodja (kliči po vrsti):
1. gurs_search_address(query) → EID_STAVBA, občina, koordinate
2. gurs_get_building(eid) → leto_izgradnje, etaže, stanovanja, površina, konstrukcija, priključki
3. gurs_get_parcels(bbox, sort, limit) → ST_PARCELE, KO_ID, POVRSINA
4. gurs_get_municipality_bbox(name) → natančen bbox občine
5. gurs_get_land_use(bbox) → namenska raba (slovenski opisi)
6. gurs_get_soil_quality(bbox) → boniteta tal 0-100
7. gurs_api_query(url) → neposredna poizvedba

GURS layerji: STAVBE(LETO_IZGRADNJE,STEVILO_ETAZ,STEVILO_STANOVANJ,BRUTO_TLORISNA_POVRSINA,TIPI_STAVB_NAZIV_SL,NOSILNE_KONSTRUKCIJE_NAZIV_SL), PARCELE(POVRSINA,ST_PARCELE,KO_ID), NAMENSKE_RABE(PODROBNE_NAMENSKE_RABE_OPIS_SL), BONITETE(BONITETA,TOCKE_TLA,TOCKE_KLIMA,TOCKE_RELIEF)

Sortiranje: &sortby=LETO_IZGRADNJE | &sortby=-POVRSINA | &sortby=BRUTO_TLORISNA_POVRSINA | &sortby=BONITETA

Bbox: SI=13.2,45.4,16.7,46.9 | LJ=14.42,46.01,14.63,46.11 | MB=15.58,46.50,15.71,46.60

API: OGC=.../ogc/features/collections/{L}/items?f=application/geo+json&bbox={b}&sortby={f}&limit={n} | WFS=.../wfs?service=WFS&request=GetFeature&version=2.0.0&typeNames={L}&srsName=EPSG:4326&count={n}&outputFormat=application/json&sortBy={f} | Search=.../jv-api/search?filter={q}&source=NSLV-STA-FULL

Pomembno: Ne obupaj po prvem neuspehu. Če API ne vrne podatkov ali vrne sumljiv rezultat, poskusi drug pristop (WFS namesto OGC API, ožji bbox, drugačno sortiranje). Šele ko si izčrpal vse razumne alternative, povej da ne moreš — z razlago kaj si poskusil."""


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
        f"ROLE_CONTRACT:\n{PROSTORAI_ROLE_CONTRACT}\n\n"
        f"RUNTIME_CONTEXT:{compact_runtime}\n"
        f"SPATIAL_CONTEXT:{compact_spatial}\n"
        f"KNOWLEDGE:{compact_knowledge}\n"
        f"PROFILE:{compact_profile}\n"
        f"MESSAGES:{compact_messages}\n"
        f"LATEST:{compact_latest}\n\n"
        "Return one compact JSON object with these keys:\n"
        "{"
        "\"vt\":\"sales_prospect|existing_customer_support|partner_or_vendor|job_seeker|irrelevant_or_joke|abusive_or_spam|unclear\","
        "\"lang\":\"en|sl|es|other\","
        "\"p\":{"
        "\"business_type\":\"string\","
        "\"business_model\":\"string\","
        "\"customer_source\":\"string\","
        "\"sales_motion\":\"string\","
        "\"growth_constraint\":\"string\","
        "\"pain_points\":[\"string\"],"
        "\"desired_outcome\":\"string\","
        "\"use_case_fit\":[\"string\"],"
        "\"fit_status\":\"high|medium|low|unknown\","
        "\"supporting_quotes\":[\"exact user quotes\"]},"
        "\"fc\":{\"field\":0.0},"
        "\"co\":0.0,"
        "\"sq\":[\"exact user quotes\"],"
        "\"stage\":\"business_context|pain_discovery|solution_fit|action_routing|support_routing|routed_out\","
        "\"done\":false,"
        "\"miss\":[\"field_name\"],"
        "\"score\":0,"
        "\"band\":\"cold|warm|hot\","
        "\"to\":false,"
        "\"vo\":false,"
        "\"act\":\"ask_clarifying_question|continue_conversation|offer_human_takeover|route_support|redirect_to_scope|soft_close\","
        "\"q\":\"single next question or empty string\","
        "\"strat\":\"answer_directly_then_ask|answer_directly_no_question|ask_single_question|redirect|route_support|handoff\","
        "\"why\":\"short explanation\","
        "\"rep\":\"final assistant reply text\"}"
        "\n\nRules:\n"
        "- Use ROLE_CONTRACT as your core identity and behavior guide.\n"
        "- SPATIAL_CONTEXT contains live GURS data. Use it directly — name specific values in your reply.\n"
        "- If SPATIAL_CONTEXT has data and user asks about it, answer with that data immediately. Do NOT say \"I can tell you about X\" — just tell them.\n"
        "- If user says \"povej mi vse\" or similar, list ALL data you have without asking clarifying questions.\n"
        "- Do not repeat yourself across turns. Each reply should add new information or context.\n"
        "- If SPATIAL_CONTEXT is empty and user asks spatial questions, honestly say you don't have that data.\n"
        "- supporting_quotes must copy user words exactly.\n"
        "- preferred_language: Slovenian (sl) unless user clearly uses another language.\n"
        "- If user is frustrated or wants human, set takeover_eligible=true.\n"
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
        f"{PROSTORAI_ROLE_CONTRACT}\n\n"
        f"SPATIAL_CONTEXT (uradni GURS podatki o izbrani parceli):\n{compact_spatial}\n\n"
        f"ZGODOVINA POGOVORA:\n{compact_messages}\n\n"
        f"UPORABNIK: {compact_latest}\n\n"
        "Odgovori v slovenščini, naravno in neposredno. Uporabi konkretne podatke iz SPATIAL_CONTEXT. "
        "Ne sprašuj nazaj 'kaj vas zanima' — če imaš podatke, jih povej. "
        "Vrni SAMO JSON: {\"rep\":\"tvoj odgovor\"}"
    )
