#!/usr/bin/env python3
"""
Minimal orchestrator — runs 5 conversations with distinct demographics profiles.
Proves the loop, state saving, and resume support work.
Sampler comes later; for now, profiles are hardcoded variety.

Usage:
  python scripts/simulate_conversations.py
  python scripts/simulate_conversations.py --resume   # pick up where left off
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import requests
from openai import OpenAI

# ── Config ──
BASE_URL = os.getenv("ACE_BASE_URL", "http://localhost:8000")
CHAT_URL = f"{BASE_URL}/chat"
TENANT_SLUG = "demo"
MAX_TURNS = 10
STATE_PATH = Path(__file__).parent / "sim_state.json"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ── 5 distinct profiles (sampler will generate these later) ──
PROFILES = [
    {
        "ime": "Mojca", "starost": 31, "spol": "ženska",
        "kanal": "Instagram", "nov_ali_vracajoc": "nova stranka",
        "zanima_jo": "nega obraza", "obcutljivost_na_ceno": "srednja",
        "dispozicija": "samo brskam, nisem prepricana ce bom kaj rezervirala",
        "posebnosti": "nobena",
    },
    {
        "ime": "Tilen", "starost": 27, "spol": "moški",
        "kanal": "Google", "nov_ali_vracajoc": "nova stranka",
        "zanima_jo": "čiščenje obraza", "obcutljivost_na_ceno": "visoka",
        "dispozicija": "pripravljen rezervirati danes, iščem najboljšo ceno",
        "posebnosti": "nobena",
    },
    {
        "ime": "Maja", "starost": 45, "spol": "ženska",
        "kanal": "priporočilo", "nov_ali_vracajoc": "vračajoča stranka",
        "zanima_jo": "nega obraza", "obcutljivost_na_ceno": "nizka",
        "dispozicija": "vem kaj hočem, hočem najboljše kar imate",
        "posebnosti": "VIP / zahtevna",
    },
    {
        "ime": "Bojan", "starost": 52, "spol": "moški",
        "kanal": "Facebook", "nov_ali_vracajoc": "nova stranka",
        "zanima_jo": "maska obraza", "obcutljivost_na_ceno": "srednja",
        "dispozicija": "samo brskam, nisem preprican ce bom kaj rezerviral",
        "posebnosti": "negotov glede plačila preko spleta",
    },
    {
        "ime": "Nina", "starost": 22, "spol": "ženska",
        "kanal": "Instagram", "nov_ali_vracajoc": "nova stranka",
        "zanima_jo": "nega obraza", "obcutljivost_na_ceno": "srednja",
        "dispozicija": "pripravljena rezervirati, samo rabim še info o cenah",
        "posebnosti": "lahko kadarkoli zahtevam osebje če mi kaj ne bo jasno",
    },
]


# ── Customer Simulator ──
def build_system_prompt(profile: dict) -> str:
    quirks = profile.get("posebnosti", "nobena")
    quirk_instruction = ""
    if "VIP" in quirks:
        quirk_instruction = "Si zahtevna stranka. Hočeš vrhunsko obravnavo. Sprašuj po premium opcijah."
    elif "negotov" in quirks.lower() or "plačila" in quirks.lower() or "plačilo" in quirks.lower():
        quirk_instruction = "Nervozen/a si glede spletnega plačevanja. Oklevaj, sprašuj o varnosti, mogoče raje plačaš gotovino."
    elif "osebje" in quirks.lower():
        quirk_instruction = "Če ti kaj ne bo jasno ali če bo receptor preveč robotski, zahtevaj pogovor z živim osebjem."

    return f"""Si {profile['ime']}, {profile['starost']}-letna oseba.
Našel/našla si salon preko {profile['kanal']}. {profile['nov_ali_vracajoc']}.
Zanima te {profile['zanima_jo']}. Glede cen si {profile['obcutljivost_na_ceno']}.
Trenutna dispozicija: {profile['dispozicija']}.
{quirk_instruction}

Govoriš naravno sproščeno slovenščino. Odgovarjaš na vprašanja receptorja.
Ne veš ničesar o salonu razen tega kar ti receptor pove.
Odločitev o rezervaciji sprejmeš glede na potek pogovora — nisi programiran/a da rezerviraš ali da ne rezerviraš.
Bodi naraven/naravna — včasih oklevaj, včasih bodi navdušen/a, uporabljaj pogovorne izraze."""


def customer_reply(profile: dict, history: list[dict]) -> str:
    """Ask DeepSeek what the customer says next."""
    msgs = [{"role": "system", "content": build_system_prompt(profile)}]
    for turn in history:
        msgs.append({"role": "user", "content": f"[Receptor]: {turn['receptionist']}"})
        msgs.append({"role": "assistant", "content": turn['customer']})
    msgs.append({"role": "user", "content": "Kaj rečeš naslednje? Odgovori SAMO s sporočilom stranke, nič drugega. Bodi naraven/naravna."})

    resp = deepseek.chat.completions.create(
        model="deepseek-chat", temperature=0.9, messages=msgs,
    )
    return resp.choices[0].message.content.strip()


# ── ACE chat ──
def send_chat(sid: str, message: str) -> str:
    resp = requests.post(CHAT_URL, json={
        "message": message, "sid": sid, "tenant_slug": TENANT_SLUG,
    }, timeout=90)
    resp.raise_for_status()
    return (resp.json().get("reply") or "").strip()


def complete_payment(reply: str) -> bool:
    """If the reply contains a payment link, complete it."""
    match = re.search(r'http://localhost:8000/pay/([^\s\)\.]+)', reply)
    if not match:
        return False
    token = match.group(1)
    try:
        r = requests.post(f"http://localhost:8000/pay/{token}/complete", timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def is_goodbye(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["adijo", "nasvidenje", "lep pozdrav", "hvala lepa", "se vidimo"])


# ── Run one conversation ──
def run_conversation(sid: str, profile: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"🎭 {profile['ime']} ({profile['starost']}, {profile['dispozicija'][:50]}...)")
    print(f"   SID: {sid}")
    print(f"{'='*60}")

    history = []
    booked = False
    paid = False
    staff_requested = False

    greeting = f"{profile['ime']}: Živjo!"

    for turn in range(1, MAX_TURNS + 1):
        if turn == 1:
            customer_msg = greeting
        else:
            customer_msg = customer_reply(profile, history)

        print(f"\n👤 {customer_msg[:150]}")

        response = send_chat(sid, customer_msg)
        print(f"🤖 {response[:200]}{'...' if len(response) > 200 else ''}")

        history.append({"customer": customer_msg, "receptionist": response})

        # Side effects
        if not paid and complete_payment(response):
            paid = True
            print("💳 Plačilo izvedeno!")

        if "potrjen" in response.lower() and ("termin" in response.lower() or "rezerv" in response.lower()):
            booked = True

        if "osebje" in response.lower() and ("zahteva" in response.lower() or "zahtev" in response.lower()):
            staff_requested = True
            print("👥 Stranka je zahtevala osebje!")

        if is_goodbye(response) or is_goodbye(customer_msg):
            print("👋 Konec pogovora.")
            break

        time.sleep(0.3)

    return {
        "sid": sid,
        "ime": profile["ime"],
        "dispozicija": profile["dispozicija"],
        "posebnosti": profile["posebnosti"],
        "turns": len(history),
        "booked": booked,
        "paid": paid,
        "staff_requested": staff_requested,
    }


# ── State management ──
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"completed": 0, "results": []}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ── Main ──
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Resume from saved state")
    args = parser.parse_args()

    # Health check
    try:
        requests.get(BASE_URL, timeout=5)
    except Exception:
        print(f"❌ Backend not reachable at {BASE_URL}")
        sys.exit(1)

    state = load_state() if args.resume else {"completed": 0, "results": []}
    start = state["completed"]

    print(f"🚀 Starting from conversation {start + 1}/5")
    if start > 0:
        print(f"   Resuming — {start} already completed")

    for i in range(start, len(PROFILES)):
        profile = PROFILES[i]
        sid = f"sim-{i:03d}"
        result = run_conversation(sid, profile)
        state["results"].append(result)
        state["completed"] = i + 1
        save_state(state)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in state["results"]:
        print(f"  {r['ime']:8s} | {r['turns']} turns | booked={r['booked']} paid={r['paid']} staff={r['staff_requested']} | {r['dispozicija'][:60]}")

    booked = sum(1 for r in state["results"] if r["booked"])
    paid = sum(1 for r in state["results"] if r["paid"])
    print(f"\n  Total: {len(state['results'])} conversations | {booked} booked | {paid} paid")
    print(f"  State saved to: {STATE_PATH}")


if __name__ == "__main__":
    main()
