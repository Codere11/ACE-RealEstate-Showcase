"""GURS tools — intent-based. LLM says what it wants, deterministic layer executes."""

import json
import math
import urllib.parse
import urllib.request
import logging

logger = logging.getLogger("ace.tools")

_SLOVENIA_BBOX = "13.2,45.4,16.7,46.9"
_BASE_OGCN = "https://ipi.eprostor.gov.si/wfs-si-gurs-kn/ogc/features"
_BASE_OGCR = "https://ipi.eprostor.gov.si/wfs-si-gurs-rpe/ogc/features"
_BASE_WFS = "https://ipi.eprostor.gov.si/wfs-si-gurs-kn/wfs"
_BASE_WFS_EV = "https://ipi.eprostor.gov.si/wfs-si-gurs-ev/wfs"
_BASE_SEARCH = "https://ipi.eprostor.gov.si/jv-api/search"

# Municipality bbox cache — loaded once, avoids 7s penalty per query
_muni_cache: dict = {}
# Cadastral municipality name cache — KO_ID → name
_ko_cache: dict = {}


def _fetch(url: str) -> dict:
    url = url.replace("application/geo+json", "application/geo%2Bjson")
    req = urllib.request.Request(url, headers={"User-Agent": "ProstorAI/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _d96_to_wgs(e: float, n: float) -> tuple:
    lat0, lon0, k0 = 0, math.radians(15), 0.9999
    a, f = 6378137.0, 1 / 298.257222101
    e2 = 2 * f - f * f
    x, y = e - 500000, n + 5000000
    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = mu + (3 * e1 / 2) * math.sin(2 * mu) + (21 * e1 ** 2 / 16) * math.sin(4 * mu)
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    t1, c1 = math.tan(phi1) ** 2, e2 / (1 - e2) * math.cos(phi1) ** 2
    d = x / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (d ** 2 / 2)
    lon = lon0 + d / math.cos(phi1)
    return (math.degrees(lat), math.degrees(lon))


# ── Tools the LLM can call ──

GURS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "gurs_search_address",
            "description": "Išči naslov v GURS bazi. Vrne naslove z EID stavbe, občino in koordinatami.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Iskalni niz, npr. 'Resljeva cesta 10 Ljubljana'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_building",
            "description": "Pridobi vse podatke o stavbi po EID: status, leto izgradnje in obnove fasade, etaže (tudi katera je pritličje), stanovanja, poslovni prostori, konstrukcija, priključki (elektrika, voda, kanalizacija, plin), bruto površina, višinske kote (najnižja, najvišja, karakteristična), katastrska občina (ID in ime), tip stavbe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "eid": {"type": "string", "description": "EID stavbe iz gurs_search_address"}
                },
                "required": ["eid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_building_parts",
            "description": "Pridobi dele stavbe (stanovanja, poslovne prostore) z EID stavbe. Vrne: številko dela, dejansko rabo (stanovanje/poslovni prostor), uporabno in neto tlorisno površino, etažo, prisotnost dvigala, leto obnove inštalacij in oken, podatek o etažni lastnini. Uporabi ko uporabnik sprašuje o stanovanjih, poslovnih prostorih ali posameznih delih stavbe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "eid": {"type": "string", "description": "EID stavbe"},
                    "limit": {"type": "integer", "description": "Max delov stavbe, privzeto 10"}
                },
                "required": ["eid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_building_addresses",
            "description": "Pridobi vse naslove stavbe po EID (ulica, hišna številka, naselje, občina, pošta). Uporabi ko uporabnik vpraša 'kateri naslovi so v tej stavbi' ali 'na katerih naslovih je ta stavba'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "eid": {"type": "string", "description": "EID stavbe"}
                },
                "required": ["eid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_parcels",
            "description": "Pridobi podatke o parcelah v območju (bbox v WGS84: minLon,minLat,maxLon,maxLat). Lahko sortiraš po površini in omejiš število. Vrne: parcelne številke, KO_ID, površine v m².",
            "parameters": {
                "type": "object",
                "properties": {
                    "bbox": {"type": "string", "description": "Bbox: 'minLon,minLat,maxLon,maxLat', npr. '14.4,46.0,14.6,46.1' za Ljubljano"},
                    "sort": {"type": "string", "enum": ["largest", "smallest", "none"], "description": "Sortiranje po površini"},
                    "limit": {"type": "integer", "description": "Max število rezultatov, privzeto 5"}
                },
                "required": ["bbox"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_municipality_bbox",
            "description": "Pridobi točne meje (bbox) občine po imenu. Uporabi PRED gurs_get_parcels da dobiš natančen bbox občine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Ime občine, npr. 'Ljubljana', 'Maribor'"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_land_use",
            "description": "Pridobi namensko rabo (prostorsko načrtovanje) za območje (bbox). Vrne človeško berljive opise v slovenščini, npr. 'CD — druga območja centralnih dejavnosti'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bbox": {"type": "string", "description": "Bbox: 'minLon,minLat,maxLon,maxLat'"}
                },
                "required": ["bbox"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_actual_land_use",
            "description": "Pridobi dejansko rabo zemljišča (ne namensko!) za območje (bbox). Vrne opis dejanske rabe v slovenščini (npr. 'pozidano zemljišče', 'gozd', 'kmetijsko zemljišče', 'stanovanjska raba').",
            "parameters": {
                "type": "object",
                "properties": {
                    "bbox": {"type": "string", "description": "Bbox: 'minLon,minLat,maxLon,maxLat'"}
                },
                "required": ["bbox"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_soil_quality",
            "description": "Pridobi boniteto tal (0-100) za območje (bbox). Vrne skupno oceno in razčlenitev na tla, podnebje, relief.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bbox": {"type": "string", "description": "Bbox: 'minLon,minLat,maxLon,maxLat'"}
                },
                "required": ["bbox"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_mass_valuation",
            "description": "Pridobi podatke o množičnem vrednotenju stavbe (EV) po EID: leto izgradnje (EV vir), leto obnove strehe, število etaž, površina, tip konstrukcije, tip stavbe, ZPS šifra. Uporabi ko uporabnik sprašuje o vrednosti nepremičnine, letu obnove strehe ali podatkih iz vrednotenja.",
            "parameters": {
                "type": "object",
                "properties": {
                    "eid": {"type": "string", "description": "EID stavbe"}
                },
                "required": ["eid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_get_utility_summary",
            "description": "Pridobi povzetek komunalne opremljenosti za območje (bbox) iz KGI (Kataster gospodarske javne infrastrukture): elektrika, vodovod, kanalizacija, plin, telekomunikacije, toplovod. Vrne 'Da' ali 'Ni podatka' za vsako omrežje.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bbox": {"type": "string", "description": "Bbox: 'minLon,minLat,maxLon,maxLat'"}
                },
                "required": ["bbox"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gurs_api_query",
            "description": "Neposredna GURS API poizvedba. Uporabi SAMO kadar specifična orodja ne zadoščajo. ZNANJE: STAVBE ima polje LETO_IZGRADNJE (podpira sortby=LETO_IZGRADNJE za najstarejše/najnovejše). PARCELE ima POVRSINA (sortby=-POVRSINA). Bazni URL za OGC API: https://ipi.eprostor.gov.si/wfs-si-gurs-kn/ogc/features/collections/{layer}/items?f=application/geo+json&bbox=...&sortby=...&limit=... Primer: najstarejša stavba v Sloveniji → /collections/SI.GURS.KN:STAVBE/items?f=application/geo+json&bbox=13.2,45.4,16.7,46.9&sortby=LETO_IZGRADNJE&limit=1. Vrni SAMO prejete podatke.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Celoten GURS API URL"},
                    "purpose": {"type": "string", "description": "Kratek namen poizvedbe"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "no_tools_needed",
            "description": "Samo kadar uporabnik pozdravi ali vodi pogovor ki ne potrebuje GURS podatkov.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


def _load_municipality_cache():
    """Pre-load all municipality bboxes and cadastral municipality names. Called once on first query."""
    global _muni_cache, _ko_cache
    if _muni_cache:
        return
    data = _fetch(f"{_BASE_OGCR}/collections/SI.GURS.RPE:OBCINE/items?f=application/geo%2Bjson&bbox={_SLOVENIA_BBOX}&limit=212")
    for f in (data.get("features") or []):
        name = (f["properties"].get("NAZIV") or "").lower()
        coords = f["geometry"]["coordinates"]
        lons, lats = [], []
        for ring in coords:
            for pt in ring:
                lons.append(pt[0]); lats.append(pt[1])
        _muni_cache[name] = f"{min(lons):.4f},{min(lats):.4f},{max(lons):.4f},{max(lats):.4f}"
    # Load cadastral municipality names (KO_ID → name, e.g. 1735 → STOŽICE)
    try:
        ko_data = _fetch(f"{_BASE_OGCN}/collections/SI.GURS.KN:KATASTRSKE_OBCINE/items?f=application/geo%2Bjson&bbox={_SLOVENIA_BBOX}&limit=3000")
        for f in (ko_data.get("features") or []):
            p = f["properties"]
            ko_id = p.get("KO_ID") or p.get("KO_SIFRA")
            ko_name = p.get("KO_NAZIV") or p.get("NAZIV")
            if ko_id and ko_name:
                _ko_cache[str(ko_id)] = str(ko_name)
        logger.warning(f"Municipality cache loaded: {len(_muni_cache)} občin, {len(_ko_cache)} katastrskih občin")
    except Exception as e:
        logger.warning(f"KO name cache load failed (non-fatal): {e}")


def _ko_name(ko_id) -> str:
    """Resolve cadastral municipality ID to name, e.g. 1735 → STOŽICE."""
    _load_municipality_cache()
    return _ko_cache.get(str(ko_id), str(ko_id))


def execute_tool(name: str, args: dict) -> str:
    """Execute intent — deterministic, no LLM URL construction."""
    try:
        if name == "no_tools_needed":
            return json.dumps({"ok": True})

        if name == "gurs_api_query":
            url = args["url"]
            url = url.replace("application/geo+json", "application/geo%2Bjson")
            # Note: OGC API sortby on whole Slovenia is unreliable — let LLM discover this from results
            try:
                data = _fetch(url)
            except Exception as e:
                return json.dumps({"napaka": f"Poizvedba ni uspela: {str(e)[:200]}. Poskusi z ožjim območjem ali drugim pristopom."}, ensure_ascii=False)
            feats = data.get("features") or []
            total = data.get("numberMatched", len(feats))
            # Validate: flag obviously wrong results
            warnings = []
            has_sortby = "sortby=" in url.lower() or "sortBy=" in url
            is_si = "13.2,45.4,16.7,46.9" in url.replace("%2C",",")
            if has_sortby and is_si:
                warnings.append("POZOR: OGC API sortby na celi SI NE vrne globalno sortiranih rezultatov. Ta rezultat NI nujno pravilen! Poskusi WFS sortBy ali zoži na občino.")
            if feats:
                # Check for suspiciously recent "oldest" results
                years = [f["properties"].get("LETO_IZGRADNJE") for f in feats if f["properties"].get("LETO_IZGRADNJE")]
                if years and min(y for y in years if y) > 1950 and "LETO_IZGRADNJE" in url:
                    warnings.append("POZOR: Najdena leta izgradnje so vsa po 1950 — to je skoraj zagotovo napačno za 'najstarejšo' stavbo. OGC API ne sortira globalno. Uporabi WFS ali zoži obseg.")
            if warnings:
                data["_warnings"] = warnings
            # Truncate to avoid overwhelming LLM
            if len(feats) > 5:
                data["features"] = feats[:5]
                data["_note"] = f"Vrnjenih {len(feats[:5])} od {total}. Zoži poizvedbo za več."
            raw = json.dumps(data, ensure_ascii=False)
            if len(raw) > 6000:
                data["features"] = feats[:2]
                data["_note"] = "Rezultat skrajšan. Uporabi bolj specifične parametre."
                raw = json.dumps(data, ensure_ascii=False)
            return raw

        if name == "gurs_search_address":
            q = urllib.parse.quote(args["query"])
            data = _fetch(f"{_BASE_SEARCH}?filter={q}&source=NSLV-STA-FULL")
            results = []
            for f in (data.get("features") or [])[:6]:
                p = f["properties"]
                lat, lon = _d96_to_wgs(float(p["E"]), float(p["N"]))
                results.append({
                    "naslov": f"{p.get('ULICA_NAZIV','')} {p.get('HS_STEVILKA','')}, {p.get('NASELJE_NAZIV','')}",
                    "obcina": p.get("OBCINA_NAZIV"),
                    "eid_stavba": p.get("EID_STAVBA"),
                    "lat": round(lat, 6), "lon": round(lon, 6),
                })
            return json.dumps({"rezultati": results, "stevilo": len(results)}, ensure_ascii=False)

        if name == "gurs_get_building":
            eid = args["eid"]
            cql = urllib.parse.quote(f"EID_STAVBA='{eid}'")
            data = _fetch(f"{_BASE_WFS}?service=WFS&request=GetFeature&version=2.0.0&typeNames=SI.GURS.KN:STAVBE&srsName=EPSG:4326&count=1&outputFormat=application/json&cql_filter={cql}")
            feats = data.get("features") or []
            if not feats:
                return json.dumps({"napaka": f"Stavba {eid} ni najdena"}, ensure_ascii=False)
            p = feats[0]["properties"]
            ko_id = p.get("KO_ID")
            return json.dumps({"stavba": {
                "eid": eid,
                "status": p.get("STATUSI_VPISA_STAVBE_NAZIV_SL"),
                "st_stavbe": p.get("ST_STAVBE"),
                "tip": p.get("TIPI_STAVB_NAZIV_SL"),
                "leto_izgradnje": p.get("LETO_IZGRADNJE"),
                "leto_obnove_fasade": p.get("LETO_OBNOVE_FASADE"),
                "stevilo_etaz": p.get("STEVILO_ETAZ"),
                "pritlicje_etaza": p.get("STEVILO_PRITLICNE_ETAZE") or p.get("ETAZA_PRITLICJE"),
                "stevilo_stanovanj": p.get("STEVILO_STANOVANJ"),
                "stevilo_poslovnih_prostorov": p.get("STEVILO_POSLOVNIH_PROSTOROV"),
                "bruto_povrsina_m2": p.get("BRUTO_TLORISNA_POVRSINA"),
                "konstrukcija": p.get("NOSILNE_KONSTRUKCIJE_NAZIV_SL"),
                "visina_najnizja_m": p.get("VISINA_H1"),
                "visina_najvisja_m": p.get("VISINA_H2"),
                "visina_karakteristicna_m": p.get("VISINA_H3"),
                "elektrika": p.get("ELEKTRIKA_NAZIV_SL"),
                "vodovod": p.get("VODOVOD_NAZIV_SL"),
                "kanalizacija": p.get("KANALIZACIJA_NAZIV_SL"),
                "plinovod": p.get("PLINOVOD_NAZIV_SL"),
                "toplotna_energija": p.get("TOPLOTNA_ENERGIJA_NAZIV_SL"),
                "obcina": p.get("RPE_OBCINE_NAZIV"),
                "ko_id": ko_id,
                "ko_ime": _ko_name(ko_id) if ko_id else None,
                "natancnost_polozaja": p.get("POLOZAJNE_NATANCNOSTI_STAVBE_NAZIV_SL"),
            }}, ensure_ascii=False)

        if name == "gurs_get_parcels":
            bbox = args["bbox"]
            sort = args.get("sort", "none")
            limit = int(args.get("limit", 5))
            url = f"{_BASE_OGCN}/collections/SI.GURS.KN:OSNOVNI_PARCELE/items?f=application/geo%2Bjson&bbox={bbox}&limit={limit}"
            if sort == "largest":
                url += "&sortby=-POVRSINA"
            elif sort == "smallest":
                url += "&sortby=POVRSINA"
            data = _fetch(url)
            results = [{
                "st_parcele": f["properties"].get("ST_PARCELE"),
                "ko_id": f["properties"].get("KO_ID"),
                "ko_ime": _ko_name(f["properties"].get("KO_ID")),
                "povrsina_m2": f["properties"].get("POVRSINA"),
            } for f in (data.get("features") or [])[:limit]]
            total = data.get("numberMatched", len(results))
            return json.dumps({"parcele": results, "stevilo_vseh": total}, ensure_ascii=False)

        if name == "gurs_get_municipality_bbox":
            _load_municipality_cache()
            wanted = (args["name"] or "").strip().lower()
            # Exact match
            if wanted in _muni_cache:
                return json.dumps({"obcina": args["name"], "bbox": _muni_cache[wanted]}, ensure_ascii=False)
            # Partial match
            for name, bbox in _muni_cache.items():
                if wanted in name:
                    return json.dumps({"obcina": name.title(), "bbox": bbox}, ensure_ascii=False)
            return json.dumps({"napaka": f"Občina '{args['name']}' ni najdena. Na voljo: {', '.join(sorted(_muni_cache.keys())[:10])}..."}, ensure_ascii=False)

        if name == "gurs_get_land_use":
            bbox = args["bbox"]
            data = _fetch(f"{_BASE_OGCN}/collections/SI.GURS.KN:NAMENSKE_RABE/items?f=application/geo%2Bjson&bbox={bbox}&limit=5")
            results = []
            for f in (data.get("features") or [])[:5]:
                p = f["properties"]
                results.append(p.get("PODROBNE_NAMENSKE_RABE_OPIS_SL") or p.get("PODROBNE_NAMENSKE_RABE_NAZIV_SL", ""))
            return json.dumps({"namenska_raba": [r for r in results if r]}, ensure_ascii=False)

        if name == "gurs_get_actual_land_use":
            bbox = args["bbox"]
            data = _fetch(f"{_BASE_OGCN}/collections/SI.GURS.KN:DEJANSKE_RABE/items?f=application/geo%2Bjson&bbox={bbox}&limit=5")
            results = []
            for f in (data.get("features") or [])[:5]:
                p = f["properties"]
                raba = p.get("MASKA_IME") or p.get("RABA_NAZIV_SL") or p.get("DEJANSKA_RABA_NAZIV_SL", "")
                if raba:
                    results.append(raba)
            return json.dumps({"dejanska_raba": results}, ensure_ascii=False)

        if name == "gurs_get_soil_quality":
            bbox = args["bbox"]
            data = _fetch(f"{_BASE_OGCN}/collections/SI.GURS.KN:BONITETE/items?f=application/geo%2Bjson&bbox={bbox}&limit=3")
            results = []
            for f in (data.get("features") or [])[:3]:
                p = f["properties"]
                results.append({
                    "boniteta": p.get("BONITETA"),
                    "tocke_tla": p.get("TOCKE_TLA"),
                    "tocke_podnebje": p.get("TOCKE_KLIMA"),
                    "tocke_relief": p.get("TOCKE_RELIEF"),
                })
            return json.dumps({"bonitete_tal": results}, ensure_ascii=False)

        if name == "gurs_get_building_parts":
            eid = args["eid"]
            limit = int(args.get("limit", 10))
            cql = urllib.parse.quote(f"EID_STAVBA='{eid}'")
            data = _fetch(f"{_BASE_WFS}?service=WFS&request=GetFeature&version=2.0.0&typeNames=SI.GURS.KN:DELI_STAVB&srsName=EPSG:4326&count={limit}&outputFormat=application/json&cql_filter={cql}")
            feats = data.get("features") or []
            if not feats:
                return json.dumps({"deli_stavbe": [], "stevilo": 0}, ensure_ascii=False)
            results = []
            for f in feats[:limit]:
                p = f["properties"]
                results.append({
                    "st_dela": p.get("ST_DELA_STAVBE") or p.get("ST_STANOVANJA"),
                    "naslov": p.get("NASLOV_DELA_STAVBE"),
                    "dejanska_raba": p.get("VRSTE_DEJANSKIH_RAB_DEL_ST_NAZIV_SL"),
                    "uporabna_povrsina_m2": p.get("UPORABNA_POVRSINA"),
                    "neto_povrsina_m2": p.get("POVRSINA"),
                    "stevilka_etaze": p.get("ETAZE_DELA_STAVBE"),
                    "st_etaze_vhoda": p.get("ST_ETAZE_GLAVNEGA_VHODA"),
                    "dvigalo": p.get("DVIGALO_NAZIV_SL"),
                    "leto_obnove_instalacij": p.get("LETO_OBNOVE_INSTALACIJ"),
                    "leto_obnove_oken": p.get("LETO_OBNOVE_OKEN"),
                    "etazna_lastnina": p.get("ETAZNA_LASTNINA_NAZIV_SL"),
                    "skupni_del": p.get("SKUPNI_DEL_ETAZNA_LASTNINA_NAZIV_SL"),
                    "upravnik": p.get("NAZIV"),
                    "upravnik_status": p.get("STATUSI_UPRAVNIKOV_NAZIV_SL"),
                })
            total = data.get("numberMatched", len(results))
            return json.dumps({"deli_stavbe": results, "stevilo": total}, ensure_ascii=False)

        if name == "gurs_get_building_addresses":
            eid = args["eid"]
            cql = urllib.parse.quote(f"EID_STAVBA='{eid}'")
            data = _fetch(f"{_BASE_WFS}?service=WFS&request=GetFeature&version=2.0.0&typeNames=SI.GURS.KN:NASLOVI_HS&srsName=EPSG:4326&count=50&outputFormat=application/json&cql_filter={cql}")
            feats = data.get("features") or []
            results = []
            for f in feats[:20]:
                p = f["properties"]
                results.append({
                    "ulica": p.get("ULICA_NAZIV"),
                    "hisna_st": p.get("HS_STEVILKA"),
                    "naselje": p.get("NASELJE_NAZIV"),
                    "obcina": p.get("OBCINA_NAZIV"),
                    "posta": p.get("POSTNI_OKOLIS_NAZIV") or p.get("POSTA_STEVILKA"),
                })
            return json.dumps({"naslovi": results, "stevilo": len(results)}, ensure_ascii=False)

        if name == "gurs_get_mass_valuation":
            eid = args["eid"]
            cql = urllib.parse.quote(f"EID_STAVBA='{eid}'")
            data = _fetch(f"{_BASE_WFS_EV}?service=WFS&request=GetFeature&version=2.0.0&typeNames=SI.GURS.EV:STAVBA&srsName=EPSG:4326&count=1&outputFormat=application/json&cql_filter={cql}")
            feats = data.get("features") or []
            if not feats:
                return json.dumps({"napaka": f"Podatki EV za stavbo {eid} niso na voljo (množično vrednotenje morda ni objavljeno za to stavbo)"}, ensure_ascii=False)
            p = feats[0]["properties"]
            return json.dumps({"vrednotenje": {
                "leto_izgradnje": p.get("LETO_IZG_STA"),
                "leto_obnove_strehe": p.get("LETO_OBN_STREHE"),
                "stevilo_etaz": p.get("ST_ETAZ"),
                "povrsina_m2": p.get("POV_STAVBE"),
                "konstrukcija": p.get("NAZIV_KONSTRUKCIJA"),
                "tip_stavbe": p.get("NAZIV_TIP_STAVBE"),
                "zps_stavba": p.get("ZPS_STAVBA"),
                "st_parcel_pod_stavbo": p.get("ST_PAR_STAVBE"),
            }}, ensure_ascii=False)

        if name == "gurs_get_utility_summary":
            bbox = args["bbox"]
            # Expand bbox ~500m for KGI (KGI layers can be sparse in dense urban areas at tight bbox)
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) == 4:
                pad = 0.005  # ~500m
                wide_bbox = f"{parts[0]-pad},{parts[1]-pad},{parts[2]+pad},{parts[3]+pad}"
            else:
                wide_bbox = bbox
            # Quick existence check for key utility layers via KGI WFS
            utility_layers = {
                "elektrika": "POLIGONI_ELEKTRICNA_ENERGIJA_G",
                "vodovod": "POLIGONI_VODOVOD_G",
                "kanalizacija": "POLIGONI_KANALIZACIJA_G",
                "plin": "POLIGONI_ZEMELJSKI_PLIN_G",
                "telekomunikacije": "POLIGONI_ELEKTRONSKE_KOMUNIKACIJE_G",
                "toplovod": "POLIGONI_TOPLOTNA_ENERGIJA_G",
            }
            results = {}
            for label, layer in utility_layers.items():
                try:
                    url = f"https://ipi.eprostor.gov.si/wfs-si-gurs-kgi/wfs?service=WFS&request=GetFeature&version=2.0.0&typeNames=SI.GURS.KGI:{layer}&srsName=EPSG:4326&count=1&outputFormat=application/json&bbox={wide_bbox.replace(',','%2C')},EPSG:4326"
                    d = _fetch(url)
                    results[label] = "Da" if (d.get("features") or d.get("numberMatched")) else "Ni podatka"
                except Exception:
                    results[label] = "Ni podatka"
            return json.dumps({"komunalna_opremljenost": results}, ensure_ascii=False)

        return json.dumps({"napaka": f"Neznano orodje: {name}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return json.dumps({"napaka": str(e)[:300]}, ensure_ascii=False)
