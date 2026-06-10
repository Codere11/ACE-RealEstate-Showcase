#!/usr/bin/env python3 -u
"""
B2B ACE Conversation Simulator

Simulates realistic Slovenian business prospects visiting the ACE website.
Each persona plays naturally — chats, shares business details, requests staff,
books calls, or drops off based on how helpful the AI is.

Staff request flow:
  - Personas with higher urgency and lower patience may request to talk to a human
  - When they do, the script calls the request-staff API → lead appears in dashboard
  - The dashboard lead card gets highlighted (lime-green) and bumped to top

Usage:
  python scripts/simulate_b2b.py              # 30 conversations
  python scripts/simulate_b2b.py --total 50   # override count
  python scripts/simulate_b2b.py --resume     # pick up where left off
  python scripts/simulate_b2b.py --staff-bias # more staff requests

Requires:
  - Backend running at http://localhost:8000
  - DEEPSEEK_API_KEY env var set
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

import requests
from openai import OpenAI

BASE_URL = os.getenv("ACE_BASE_URL", "http://localhost:8000")
CHAT_URL = f"{BASE_URL}/chat"
TENANT_SLUG = "demo"
MAX_TURNS = 7
STATE_PATH = Path(__file__).parent / "sim_b2b_state.json"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    print("DEEPSEEK_API_KEY not set")
    sys.exit(1)

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


# ═══════════════════════════════════════════════════════════
#  B2B Personas (weight, name, role, company, pain, urgency, patience, staff_likelihood, opening_line)
# ═══════════════════════════════════════════════════════════

PERSONAS = [
    (6, "Miha", "CTO SaaS podjetja", "CloudTool d.o.o., 15 zaposlenih",
     "Izgubljajo lead-e ker ni avtomatizacije, vse gre preko emaila",
     "ta mesec", "srednja", 0.15,
     "Zivjo, zanima me vasa resitev za avtomatizacijo sprejema strank. Mi lahko poveste vec?"),
    (8, "Ana", "Vodja prodaje v kliniki", "Dermamed, 30 zaposlenih",
     "Recepcionistka je preobremenjena, klici zamujajo, narocanje je kaos",
     "ta mesec", "visoka", 0.35,
     "Dober dan, imamo kliniko in iscemo nekaj kar bi nam olajsalo narocanje in klice. Kaj tocno ponujate?"),
    (10, "Bostjan", "Lastnik e-commerce trgovine", "SportPlus.si, 8 zaposlenih",
     "Veliko obiskovalcev spletne strani, nihce ne ve kaj hocejo, prodaja trpi",
     "letos", "srednja", 0.20,
     "Hej, slisal sem za vas na LinkedInu. Kako tocno deluje ta AI receptor?"),
    (5, "Klavdija", "Marketing direktorica B2B agencije", "Rast d.o.o., 22 zaposlenih",
     "Stranke pricakujejo takojsen odgovor, oni so na sestankih, izgubljajo posle",
     "jutri", "visoka", 0.45,
     "Nujno potrebujemo nekaj za avtomatske odgovore strankam. Delate tudi integracije s HubSpotom?"),
    (8, "Tomas", "IT vodja v proizvodnem podjetju", "Kovinarstvo Novak, 50 zaposlenih",
     "Spletna stran je tam ze 5 let, nic ne deluje, potrebujejo celovito prenovo",
     "letos", "nizka", 0.10,
     "Dober dan, rabili bi modernizacijo nase spletne strani in mogoce ta AI sprejem. A lahko pomagate?"),
    (6, "Nina", "Founder startupa", "LegalBot.io, 4 zaposleni",
     "Hocejo izgledati vecji kot so, potrebujejo profesionalen prvi stik",
     "ta mesec", "visoka", 0.30,
     "Hej, startup smo, iscemo nekaj za prvi stik s strankami da zgledamo profesionalno. Delate tudi z manjsimi?"),
    (10, "Marko", "Mid-level manager logistika", "Transport & Co, 40 zaposlenih",
     "Sef mu je narocil 'pojdi na net in najdi nekaj za klice'. Nima pojma kaj isce, samo brska",
     "letos", "nizka", 0.05,
     "Zivjo, pri nas imamo problem s klici strank. Kaj bi vi predlagali?"),
    (8, "Barbara", "Head of Customer Success", "DataFlow d.o.o., 25 zaposlenih",
     "Imajo HubSpot ampak ne integrira slovenskega trga, iscejo lokalno alternativo",
     "ta mesec", "srednja", 0.25,
     "Imamo HubSpot, ampak za slovenske stranke ne deluje najboljse. A se da integrirati z vasim sistemom?"),
    (6, "Peter", "Solopreneur svetovalec", "Peter s.p., 1 zaposlen",
     "Prevec casa porabi za administrativne klice namesto za delo s strankami",
     "letos", "srednja", 0.10,
     "Dober dan, delam kot svetovalec in me zanima ce imate resitev tudi za solo podjetnike?"),
    (4, "Andrej", "Enterprise CTO", "Merkur d.d., 300 zaposlenih",
     "Razpis za digitalno transformacijo, iscejo vendor-ja za pilotni projekt",
     "ta mesec", "zelo visoka", 0.40,
     "Dober dan, iz Merkurja smo. Pripravljamo digitalno transformacijo in iscemo partnerja za AI recepcijo. Imate reference?"),
    # NEW PERSONAS
    (9, "Mateja", "Vodja nepremicninske agencije", "Nepremicnine Dom d.o.o., 12 zaposlenih",
     "Agenti so na terenu, nihce ne dvigne telefona, stranke so razocaranje",
     "ta mesec", "visoka", 0.35,
     "Dober dan, imamo nepremicninsko agencijo in iscemo resevanje za klice strank ko so agenti zunaj. Imate kaj takega?"),
    (7, "Ziga", "Direktor digitalne agencije", "PixelSmith d.o.o., 18 zaposlenih",
     "Prevec casa izgubijo z odgovarjanjem na enostavna vprasanja, hocejo avtomatizirati FAQ",
     "letos", "srednja", 0.20,
     "Hej, digitalna agencija smo. Zanima me ce imate AI klepet ki lahko odgovarja na pogosta vprasanja namesto nas. Kako to deluje?"),
    (8, "Sara", "Operations manager hotel", "Hotel Slapnik, 45 zaposlenih",
     "Recepcija gostov je drag sport, iscejo AI za prvi kontakt prek spleta",
     "ta mesec", "srednja", 0.25,
     "Dober dan, hotel imamo in razmisljamo o avtomatizaciji spletnih povprasevanj. Mi lahko razlozite vase delovanje?"),
    (6, "David", "Prodajni direktor zavarovalnice", "Zavarovalnica Varna d.d., 60 zaposlenih",
     "Generirajo veliko leadov iz spleta, a jih rocno obdelujejo predolgo",
     "ta mesec", "zelo visoka", 0.50,
     "Nujno! Imamo na stotine spletnih povprasevanj na teden in premalo ljudi. Kako hitro lahko zacnemo?"),
    (8, "Mojca", "Lastnica kozmeticnega salona", "Salon Lepote Mojca, 6 zaposlenih",
     "Stranke klicejo za termine, ona je pri stranki, nic ne gre skozi",
     "jutri", "visoka", 0.30,
     "Dober dan, kozmeticarka sem in potrebujem sistem za avtomatsko narocanje strank. Delate kaj takega? In kako hitro?"),
    (5, "Gregor", "CFO fintech startupa", "PayFlow d.o.o., 25 zaposlenih",
     "Imajo budget 50k€ za CX avtomatizacijo, hocejo vendorja za dolgorocno sodelovanje",
     "ta mesec", "visoka", 0.40,
     "Imamo budget za avtomatizacijo uporabniske podpore. Iscemo partnerja za dolgorocno sodelovanje. Kakšne so vase cene in paketi?"),
    (6, "Jasna", "HR direktorica vecjega podjetja", "Steklarna Hrastnik, 200 zaposlenih",
     "Interni IT helpdesk je preobremenjen, iscejo AI za prvo linijo podpore zaposlenim",
     "letos", "srednja", 0.15,
     "Dober dan, v HR smo in iscemo AI resitev za interni helpdesk. Ali delate tudi interne resitve ali samo za zunanje stranke?"),
    (9, "Rok", "MLOps inzenir", "DataMind d.o.o., 30 zaposlenih",
     "Tehnicni kupec, hoce vedeti arhitekturo, latenca, integracije preden se pogovarja o ceni",
     "letos", "srednja", 0.10,
     "Zivjo, MLOps inzenir tukaj. Zanima me vasa arhitektura — kako hitro se model odziva, kaksna latenca, ali podpirate custom modele? In kaksne integracije imate?"),
]


def draw_persona(staff_bias=False):
    """Weighted persona selection. staff_bias increases weight for high staff-likelihood personas."""
    weighted = []
    for p in PERSONAS:
        w = p[0]
        if staff_bias:
            # Boost high staff-likelihood personas
            w = int(w * (1.0 + p[7] * 3))
        weighted.append((w, p))
    total = sum(w for w, _ in weighted)
    r = random.randint(1, total)
    for w, p in weighted:
        r -= w
        if r <= 0:
            return p[1:]  # name, role, company, pain, urgency, patience, staff_likelihood, opening
    return PERSONAS[0][1:]


# ═══════════════════════════════════════════════════════════
#  Customer Simulator
# ═══════════════════════════════════════════════════════════

def build_customer_prompt(name, role, company, pain, urgency, patience, staff_likelihood, history, turn, wants_staff):
    parts = [
        f"Ti si {name}, {role} v podjetju {company}.",
        f"Tvoj problem: {pain}.",
        f"Urgenca: {urgency}. Potrpezljivost: {patience}.",
        f"Si na spletni strani ACE - podjetja za AI recepcijske resitve. Pises v njihov AI klepet.",
        f"O ACE ne ves nicesar razen tega kar ti AI svetovalec pove.",
        "",
        "TVOJ TON:",
        "- Naravna pogovorna slovenscina. Nisi prevec formalen, nisi prevec sproscen.",
        "- Odgovarjas na vprasanja, postavljas svoja.",
        "- Ce ti AI svetovalec pomaga in odgovarja smiselno - ostani v pogovoru.",
        "- Ce AI rece 'pustite email/telefon', 'posljem vam', 'se dogovorimo za klic' - TO JE ZNAK DA SI ZADOVOLJEN/A. Pusti kontakt ali sprejmi klic. NE sprasuj vec.",
        "- Ce se AI ponavlja, ne poslusa, ali sprasuje nesmiselne stvari - postani nestrpen/a in se poslovi.",
        "- Ne pusti kontakta takoj - pocakaj vsaj 2 izmenjavi da vidis ce je ACE zate.",
    ]

    # Staff request behavior
    if wants_staff:
        parts.append("")
        parts.append("POMEMBNO: Zdaj hoces govoriti z zivim clovekom, ne z AI-em.")
        parts.append("Recek 'ali lahko dobim cloveka/o sebje/prodajo' ali podobno.")
        parts.append("Bodi nekoliko nestrpen/a ampak ne nesramen/na. Hoces cloveski stik.")
    elif turn >= 3 and patience in ("visoka", "zelo visoka") and random.random() < 0.15:
        parts.append("")
        parts.append("POMEMBNO: Zacenjas zgubljati potrpezljivost. Ce AI ne odgovori konkretno, recek da hoces govoriti z zivim clovekom ali se poslovis.")

    if history:
        parts.append("")
        parts.append("POGOVOR DO SEDAJ:")
        for t in history:
            parts.append(f"  AI svetovalec: {t['receptionist']}")
            parts.append(f"  Ti ({name}): {t['customer']}")
        parts.append("")
        parts.append(f"AI svetovalec je ravnokar rekel: {history[-1]['receptionist']}")
        parts.append("Kaj odgovoris? Bodisi nadaljuj pogovor, pusti kontakt, zahtevaj osebje, ali se poslovi.")
        parts.append("Odgovori SAMO s svojim sporocilom, nic drugega.")
    else:
        parts.append("")
        parts.append("Zacni pogovor. Napisi prvo sporocilo AI svetovalcu.")

    return "\n".join(parts)


def customer_reply(name, role, company, pain, urgency, patience, staff_likelihood, history, turn, wants_staff):
    system = build_customer_prompt(name, role, company, pain, urgency, patience, staff_likelihood, history, turn, wants_staff)
    msgs = [{"role": "system", "content": system}]
    msgs.append({"role": "user", "content": "Tvoj odgovor:"})

    for attempt in range(3):
        try:
            temp = 0.75 + random.random() * 0.2
            resp = deepseek.chat.completions.create(
                model="deepseek-chat", temperature=temp,
                messages=msgs, timeout=30,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return ""


# ═══════════════════════════════════════════════════════════
#  ACE chat
# ═══════════════════════════════════════════════════════════

def send_chat(sid, message):
    for attempt in range(3):
        try:
            resp = requests.post(CHAT_URL, json={
                "message": message, "sid": sid, "tenant_slug": TENANT_SLUG,
            }, timeout=90)
            resp.raise_for_status()
            return (resp.json().get("reply") or "").strip()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return ""


def request_staff(sid):
    """Call the request-staff API to mark lead as staff-requested in dashboard."""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/public/organizations/{TENANT_SLUG}/leads/{sid}/request-staff",
            timeout=10
        )
        resp.raise_for_status()
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"\n   ⚠️  Staff request API failed for {sid}: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  Detection
# ═══════════════════════════════════════════════════════════

def is_call_booked(text):
    lower = text.lower()
    signals = ["discovery call", "klic potrjen", "klic je dogovorjen", "potrjeno", "se slisimo"]
    return any(s in lower for s in signals)


def has_contact(text):
    import re
    return bool(re.search(r'[\w.+-]+@[\w-]+\.[\w.+-]+', text)) or \
           bool(re.search(r'(\+?\d[\d\s]{7,}\d)', text))


def is_handoff_point(text):
    lower = text.lower()
    signals = [
        "se slisimo", "vam posljem", "bom poslal", "vam bom", "kontaktiral",
        "se povežemo", "pokličem", "poslal vam", "pošljem",
        "dogovorimo", "se dogovorimo", "slišimo",
    ]
    return any(s in lower for s in signals)


def is_goodbye(text):
    lower = text.lower()
    return any(w in lower for w in [
        "adijo", "nasvidenje", "hvala lepa", "lep dan", "se vidimo",
        "bom se razmislil", "bom razmislila", "bom premislil",
        "se oglasim", "vam sporocim", "hvala za informacije",
        "hvala za info", "hvala za pomoc",
    ])


def customer_wants_staff(text):
    """Detect if the customer is asking for a human/staff member."""
    lower = text.lower()
    signals = [
        "živo osebje", "cloveka", "človeka", "zaposlenega", "prodajnika",
        "osebje", "osebja", "živ človek", "ziv clovek", "pravi clovek",
        "pravega cloveka", "človeški stik", "cloveski stik",
        "govoriti z", "govorim z", "pogovor s", "pogovarjam z",
        "lahko dobim", "klicem", "poklicem", "kontakt osebno",
        "prodajno osebje", "sales", "prodajalca", "svetovalca",
    ]
    return any(s in lower for s in signals)


def ai_offers_staff(text):
    """Detect if the AI is offering a human/staff connection."""
    lower = text.lower()
    signals = [
        "osebje", "sodelavec", "ekipo", "team", "kolega",
        "povežem", "povezujem", "človek", "klicem",
        "prevzamem", "prevzamemo",
    ]
    return any(s in lower for s in signals)


# ═══════════════════════════════════════════════════════════
#  One conversation
# ═══════════════════════════════════════════════════════════

def run_conversation(index, persona, staff_bias=False):
    name, role, company, pain, urgency, patience, staff_likelihood, opening = persona
    sid = f"b2b-{index:03d}"
    history = []
    call_booked = False
    contact_left = False
    dropped_off = False
    staff_requested = False
    wants_staff = False
    outcome = "unknown"

    # Determine if this persona will request staff
    effective_likelihood = staff_likelihood
    if staff_bias:
        effective_likelihood = min(1.0, staff_likelihood * 2.5)

    for turn in range(1, MAX_TURNS + 1):
        # Decide staff request behavior
        if not staff_requested and not wants_staff and turn >= 2:
            # High urgency + high likelihood = more likely to request staff
            urgency_mult = {"jutri": 2.0, "ta mesec": 1.2, "letos": 0.5}.get(urgency, 1.0)
            patience_mult = {"zelo visoka": 1.5, "visoka": 1.2, "srednja": 0.8, "nizka": 0.4}.get(patience, 0.8)
            chance = effective_likelihood * urgency_mult * patience_mult * 0.3
            if random.random() < chance:
                wants_staff = True

        if turn == 1:
            customer_msg = opening
        else:
            customer_msg = customer_reply(name, role, company, pain, urgency, patience, staff_likelihood, history, turn, wants_staff)

        if not customer_msg:
            outcome = "error"
            break

        try:
            response = send_chat(sid, customer_msg)
        except Exception as e:
            print(f"\n   API error: {e}")
            outcome = "error"
            break

        history.append({"customer": customer_msg, "receptionist": response})

        # Detect staff request from customer
        if wants_staff and customer_wants_staff(customer_msg):
            staff_requested = True
            wants_staff = False
            # Actually hit the request-staff API
            api_ok = request_staff(sid)
            if api_ok:
                outcome = "staff_requested"

        # Detect call booking
        if is_call_booked(response):
            call_booked = True
            if outcome == "unknown":
                outcome = "call_booked"
            break

        # Detect contact
        if has_contact(customer_msg) and not contact_left:
            contact_left = True

        # Natural handoff: contact + AI follow-up
        if contact_left and is_handoff_point(response) and turn >= 3:
            if outcome == "unknown":
                outcome = "handoff"
            break

        # Goodbye / drop-off
        if is_goodbye(customer_msg):
            dropped_off = True
            if outcome == "unknown":
                outcome = "dropped_off"
            break

        time.sleep(0.3)

    if outcome == "unknown":
        outcome = "max_turns" if not staff_requested else "staff_requested"

    return {
        "sid": sid, "index": index,
        "name": name, "role": role, "company": company,
        "urgency": urgency, "patience": patience,
        "turns": len(history),
        "outcome": outcome,
        "call_booked": call_booked,
        "contact_left": contact_left,
        "dropped_off": dropped_off,
        "staff_requested": staff_requested,
        "history": history,
    }


# ═══════════════════════════════════════════════════════════
#  Progress & state
# ═══════════════════════════════════════════════════════════

def progress_bar(current, total, width=30):
    filled = int(width * current / total)
    bar = "=" * filled + "-" * (width - filled)
    return f"[{bar}] {current}/{total}"


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"completed": 0, "results": []}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def print_summary(results):
    n = len(results)
    if n == 0:
        return
    booked = sum(1 for r in results if r["call_booked"])
    contact = sum(1 for r in results if r["contact_left"])
    handoff = sum(1 for r in results if r["outcome"] == "handoff")
    dropped = sum(1 for r in results if r["outcome"] == "dropped_off")
    maxed = sum(1 for r in results if r["outcome"] == "max_turns")
    staff = sum(1 for r in results if r["staff_requested"])
    avg_turns = sum(r["turns"] for r in results) / n

    print(f"\n{'=' * 60}")
    print("SIMULATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Conversations:        {n}")
    print(f"  Calls booked:         {booked} ({booked/n*100:.0f}%)")
    print(f"  Staff requested:      {staff} ({staff/n*100:.0f}%)")
    print(f"  Handoff point:        {handoff} ({handoff/n*100:.0f}%)")
    print(f"  Contact left:         {contact} ({contact/n*100:.0f}%)")
    print(f"  Dropped off:          {dropped} ({dropped/n*100:.0f}%)")
    print(f"  Max turns reached:    {maxed} ({maxed/n*100:.0f}%)")
    print(f"  Avg turns:            {avg_turns:.1f}")

    print(f"\n  BY URGENCY:")
    for u in ["jutri", "ta mesec", "letos"]:
        group = [r for r in results if r["urgency"] == u]
        if group:
            b = sum(1 for r in group if r["call_booked"])
            c = sum(1 for r in group if r["contact_left"])
            s = sum(1 for r in group if r["staff_requested"])
            print(f"    {u:<12s} total={len(group):2d}  booked={b:2d}  contact={c:2d}  staff={s:2d}")

    print(f"\n  BY PATIENCE:")
    for p in ["zelo visoka", "visoka", "srednja", "nizka"]:
        group = [r for r in results if r["patience"] == p]
        if group:
            s = sum(1 for r in group if r["staff_requested"])
            d = sum(1 for r in group if r["dropped_off"])
            print(f"    {p:<15s} total={len(group):2d}  staff={s:2d}  dropped={d:2d}")

    print(f"\n  State saved: {STATE_PATH}")


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--total", type=int, default=30)
    parser.add_argument("--staff-bias", action="store_true", help="Generate more staff-request conversations")
    args = parser.parse_args()

    try:
        requests.get(f"{BASE_URL}/", timeout=5)
        print("✅ Backend reachable")
    except Exception:
        print(f"❌ Backend not reachable at {BASE_URL}")
        sys.exit(1)

    if args.resume:
        state = load_state()
    else:
        state = {"completed": 0, "results": []}

    start = state["completed"]
    total = args.total

    if start >= total:
        print("All done.")
        print_summary(state["results"])
        return

    print(f"Running {total} conversations, starting at {start+1}")
    print(f"Staff bias: {'ON' if args.staff_bias else 'OFF'}")
    print(f"Personas: {len(PERSONAS)} (including {len(PERSONAS)-10} new)\n")

    for i in range(start, total):
        persona = draw_persona(args.staff_bias)
        name, role, company, pain, urgency, patience, staff_like, _ = persona

        print(f"\n{progress_bar(i+1, total)} | {name} ({role[:30]})", flush=True)

        try:
            result = run_conversation(i, persona, args.staff_bias)
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            result = {
                "sid": f"b2b-{i:03d}", "index": i,
                "name": name, "role": role, "company": company,
                "urgency": urgency, "patience": patience,
                "turns": 0, "outcome": "error",
                "call_booked": False, "contact_left": False,
                "dropped_off": False, "staff_requested": False,
                "history": [],
            }

        # Build marker string
        parts = []
        if result["call_booked"]: parts.append("CALL")
        if result["staff_requested"]: parts.append("👥STAFF")
        if result["contact_left"]: parts.append("CONT")
        if result["dropped_off"]: parts.append("DROP")
        if result["outcome"] == "handoff": parts.append("HNDF")
        if result["outcome"] == "max_turns": parts.append("MAX")
        marker = "|".join(parts) if parts else result["outcome"]
        print(f"  {marker} {result['turns']}t | {result['outcome']}", flush=True)

        state["results"].append(result)
        state["completed"] = i + 1
        save_state(state)

    print_summary(state["results"])


if __name__ == "__main__":
    main()
