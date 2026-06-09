#!/usr/bin/env python3 -u
"""
B2B ACE Conversation Simulator

Simulates realistic Slovenian business prospects visiting the ACE website.
Each persona plays naturally, stays or leaves based on how helpful the AI is.

Usage:
  python scripts/simulate_b2b.py              # 30 conversations
  python scripts/simulate_b2b.py --total 50   # override count
  python scripts/simulate_b2b.py --resume     # pick up where left off

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
MAX_TURNS = 6
STATE_PATH = Path(__file__).parent / "sim_b2b_state.json"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    print("DEEPSEEK_API_KEY not set")
    sys.exit(1)

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


# ═══════════════════════════════════════════════════════════
#  B2B Personas
# ═══════════════════════════════════════════════════════════

PERSONAS = [
    # (weight, name, role, company, pain, urgency, patience, opening_line)
    (8, "Miha", "CTO manjsega SaaS podjetja", "CloudTool d.o.o., 15 zaposlenih",
     "Izgubljajo lead-e ker ni avtomatizacije, vse gre preko emaila",
     "ta mesec", "srednja",
     "Zivjo, zanima me vasa resitev za avtomatizacijo sprejema strank. Mi lahko poveste vec?"),
    (10, "Ana", "Vodja prodaje v kliniki", "Dermamed, 30 zaposlenih",
     "Recepcionistka je preobremenjena, klici zamujajo, narocanje je kaos",
     "ta mesec", "visoka",
     "Dober dan, imamo kliniko in iscemo nekaj kar bi nam olajsalo narocanje in klice. Kaj tocno ponujate?"),
    (12, "Bostjan", "Lastnik e-commerce trgovine", "SportPlus.si, 8 zaposlenih",
     "Veliko obiskovalcev spletne strani, nihce ne ve kaj hocejo, prodaja trpi",
     "letos", "srednja",
     "Hej, slisal sem za vas na LinkedInu. Kako tocno deluje ta AI receptor?"),
    (6, "Klavdija", "Marketing direktorica v B2B agenciji", "Rast d.o.o., 22 zaposlenih",
     "Stranke pricakujejo takojsen odgovor, oni so na sestankih, izgubljajo posle",
     "jutri", "visoka",
     "Nujno potrebujemo nekaj za avtomatske odgovore strankam. Delate tudi integracije s HubSpotom?"),
    (10, "Tomas", "IT vodja v proizvodnem podjetju", "Kovinarstvo Novak, 50 zaposlenih",
     "Spletna stran je tam ze 5 let, nic ne deluje, potrebujejo celovito prenovo",
     "letos", "nizka",
     "Dober dan, rabili bi modernizacijo nase spletne strani in mogoce ta AI sprejem. A lahko pomagate?"),
    (7, "Nina", "Founder startupa", "LegalBot.io, 4 zaposleni",
     "Hocejo izgledati vecji kot so, potrebujejo profesionalen prvi stik",
     "ta mesec", "visoka",
     "Hej, startup smo, iscemo nekaj za prvi stik s strankami da zgledamo profesionalno. Delate tudi z manjsimi?"),
    (14, "Marko", "Mid-level manager v logistiki", "Transport & Co, 40 zaposlenih",
     "Sef mu je narocil 'pojdi na net in najdi nekaj za klice'. Nima pojma kaj isce, samo brska",
     "letos", "nizka",
     "Zivjo, pri nas imamo problem s klici strank. Kaj bi vi predlagali?"),
    (10, "Barbara", "Head of Customer Success", "DataFlow d.o.o., 25 zaposlenih",
     "Imajo HubSpot ampak ne integrira slovenskega trga, iscejo lokalno alternativo",
     "ta mesec", "srednja",
     "Imamo HubSpot, ampak za slovenske stranke ne deluje najboljse. A se da integrirati z vasim sistemom?"),
    (8, "Peter", "Solopreneur - svetovalec", "Peter s.p., 1 zaposlen",
     "Prevec casa porabi za administrativne klice namesto za delo s strankami",
     "letos", "srednja",
     "Dober dan, delam kot svetovalec in me zanima ce imate resitev tudi za solo podjetnike?"),
    (5, "Andrej", "Enterprise CTO", "Merkur d.d., 300 zaposlenih",
     "Razpis za digitalno transformacijo, iscejo vendor-ja za pilotni projekt",
     "ta mesec", "zelo visoka",
     "Dober dan, iz Merkurja smo. Pripravljamo digitalno transformacijo in iscemo partnerja za AI recepcijo. Imate reference?"),
]

# Weighted sampler
def draw_persona():
    total = sum(p[0] for p in PERSONAS)
    r = random.randint(1, total)
    for p in PERSONAS:
        r -= p[0]
        if r <= 0:
            return p[1:]  # name, role, company, pain, urgency, patience, opening_line
    return PERSONAS[0][1:]


# ═══════════════════════════════════════════════════════════
#  Customer Simulator
# ═══════════════════════════════════════════════════════════

def build_customer_prompt(name, role, company, pain, urgency, patience, history):
    parts = [
        f"Ti si {name}, {role} v podjetju {company}.",
        f"Tvoj problem: {pain}.",
        f"Urgenca: {urgency}.",
        f"Si na spletni strani ACE - podjetja za AI recepcijske resitve. Pises v njihov klepet.",
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

    if history:
        parts.append("")
        parts.append("POGOVOR DO SEDAJ:")
        for turn in history:
            parts.append(f"  AI svetovalec: {turn['receptionist']}")
            parts.append(f"  Ti ({name}): {turn['customer']}")
        parts.append("")
        parts.append(f"AI svetovalec je ravnokar rekel: {history[-1]['receptionist']}")
        parts.append("Kaj odgovoris? Bodisi nadaljuj pogovor, pusti kontakt, ali se poslovi.")
        parts.append("Odgovori SAMO s svojim sporocilom, nic drugega.")
    else:
        parts.append("")
        parts.append("Zacni pogovor. Napisi prvo sporocilo AI svetovalcu.")

    return "\n".join(parts)


def customer_reply(name, role, company, pain, urgency, patience, history):
    system = build_customer_prompt(name, role, company, pain, urgency, patience, history)
    msgs = [{"role": "system", "content": system}]
    msgs.append({"role": "user", "content": "Tvoj odgovor:"})

    for attempt in range(3):
        try:
            temp = 0.8 + random.random() * 0.15
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


# ═══════════════════════════════════════════════════════════
#  One conversation
# ═══════════════════════════════════════════════════════════

def run_conversation(index, persona):
    name, role, company, pain, urgency, patience, opening = persona
    sid = f"b2b-{index:03d}"
    history = []
    call_booked = False
    contact_left = False
    dropped_off = False
    outcome = "unknown"
      # opening_line

    for turn in range(1, MAX_TURNS + 1):
        if turn == 1:
            customer_msg = opening
        else:
            customer_msg = customer_reply(name, role, company, pain, urgency, patience, history)

        try:
            response = send_chat(sid, customer_msg)
        except Exception as e:
            print(f"\n   API error: {e}")
            outcome = "error"
            break

        history.append({"customer": customer_msg, "receptionist": response})

        if is_call_booked(response):
            call_booked = True
            outcome = "call_booked"
            break

        if has_contact(customer_msg) and not contact_left:
            contact_left = True

        # Stop at natural handoff: contact captured + AI says "we'll follow up"
        if contact_left and is_handoff_point(response) and turn >= 3:
            outcome = "handoff"
            break

        if is_goodbye(customer_msg):
            dropped_off = True
            if outcome == "unknown":
                outcome = "dropped_off"
            break

        time.sleep(0.3)

    if outcome == "unknown":
        outcome = "max_turns"

    return {
        "sid": sid, "index": index,
        "name": name, "role": role, "company": company,
        "urgency": urgency, "patience": patience,
        "turns": len(history),
        "outcome": outcome,
        "call_booked": call_booked,
        "contact_left": contact_left,
        "dropped_off": dropped_off,
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
    avg_turns = sum(r["turns"] for r in results) / n

    print(f"\n{'=' * 60}")
    print("SIMULATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Conversations:       {n}")
    print(f"  Calls booked:        {booked} ({booked/n*100:.0f}%)")
    print(f"  Handoff point:       {handoff} ({handoff/n*100:.0f}%)")
    print(f"  Contact left:        {contact} ({contact/n*100:.0f}%)")
    print(f"  Dropped off:         {dropped} ({dropped/n*100:.0f}%)")
    print(f"  Max turns:           {maxed} ({maxed/n*100:.0f}%)")
    print(f"  Avg turns:           {avg_turns:.1f}")

    print(f"\n  BY URGENCY:")
    for u in ["jutri", "ta mesec", "letos"]:
        group = [r for r in results if r["urgency"] == u]
        if group:
            b = sum(1 for r in group if r["call_booked"])
            c = sum(1 for r in group if r["contact_left"])
            print(f"    {u:<12s} total={len(group):2d}  booked={b:2d}  contact={c:2d}")

    print(f"\n  State: {STATE_PATH}")


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--total", type=int, default=30)
    args = parser.parse_args()

    try:
        requests.get(f"{BASE_URL}/", timeout=5)
        print("Backend reachable")
    except Exception:
        print(f"Backend not reachable at {BASE_URL}")
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

    print(f"Running {total} conversations, starting at {start+1}\n")

    for i in range(start, total):
        persona = draw_persona()
        name, role, company = persona[0], persona[1], persona[2]

        print(f"\n{progress_bar(i+1, total)} | {name} ({role[:30]})", flush=True)

        result = run_conversation(i, persona)
        marker = "CALL" if result["call_booked"] else "HNDF" if result["outcome"] == "handoff" else "CONT" if result["contact_left"] else "DROP" if result["dropped_off"] else "MAX"
        print(f"  {marker} {result['turns']}t | {result['outcome']}", flush=True)

        state["results"].append(result)
        state["completed"] = i + 1
        save_state(state)

    print_summary(state["results"])


if __name__ == "__main__":
    main()
