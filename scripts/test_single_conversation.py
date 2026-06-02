#!/usr/bin/env python3
"""
Test a SINGLE simulated conversation through the ACE system.

Sends messages via POST /chat and reads JSON responses.
Uses DeepSeek API as the Customer Simulator (as described in Analize.md).

Prerequisites (as per Startup.txt):
  docker compose -f docker-compose-simple.yml up -d          # postgres + livekit
  cd backend && source ../venv/bin/activate && PYTHONPATH=.. uvicorn main:app --port 8000 --reload

Usage:
  python scripts/test_single_conversation.py                 # Full LLM-driven test
  python scripts/test_single_conversation.py --simple        # Hardcoded messages, no LLM
  python scripts/test_single_conversation.py --max-turns 8   # More turns
  python scripts/test_single_conversation.py --verify        # Check DB persistence
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests

# ── Project path ──
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.getenv("ACE_BASE_URL", "http://localhost:8000")
CHAT_URL = f"{BASE_URL}/chat"
TENANT_SLUG = "demo"

# ── DeepSeek Customer Simulator setup ──
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _deepseek_client():
    from openai import OpenAI
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


# ── Demographics for the test customer ──
DEMOGRAPHICS = {
    "ime": "Mojca",
    "starost": 31,
    "spol": "ženska",
    "kanal": "Instagram",
    "nov_ali_vracajoc": "nova stranka",
    "zanima_jo": "nega obraza",
    "obcutljivost_na_ceno": "srednja",
    "dispozicija": "raziskujem, nisem še odločena, ampak me res zanima",
    "posebnosti": "nobena",
}

CUSTOMER_SYSTEM_PROMPT = f"""Si {DEMOGRAPHICS['ime']}, {DEMOGRAPHICS['starost']}-letna stranka kozmetičnega salona.
Našla si nas preko {DEMOGRAPHICS['kanal']}. {DEMOGRAPHICS['nov_ali_vracajoc']}.
Zanima te {DEMOGRAPHICS['zanima_jo']}. Glede cen si {DEMOGRAPHICS['obcutljivost_na_ceno']}.
Trenutno si razpoložena: {DEMOGRAPHICS['dispozicija']}.
{DEMOGRAPHICS['posebnosti'] if DEMOGRAPHICS['posebnosti'] != 'nobena' else ''}

Govoriš naravno sproščeno slovenščino. Odgovarjaš na vprašanja receptorja.
Ne veš ničesar o salonu razen tega kar ti receptor pove.
Odločitev o rezervaciji sprejmeš glede na potek pogovora — nisi programirana da rezerviraš ali da ne rezerviraš.
Bodi naravna — včasih oklevaj, včasih bodi navdušena, uporabljaj pogovorne izraze ('a veš', 'mogoče', 'bom še razmislila')."""


# ── Hardcoded simple conversation (--simple mode) ──
SIMPLE_MESSAGES = [
    "Živjo! Zanima me, kakšne storitve imate za nego obraza?",
    "Koliko pa stane?",
    "Pa imate kaj prosto ta teden? Recimo v petek dopoldne?",
    "Super, bi rezervirala! Sem Mojca, telefon 040 123 456.",
    "Hvala, to je to zaenkrat!",
]


def send_chat(sid: str, message: str) -> str:
    """Send a message to POST /chat and return the receptionist's reply."""
    resp = requests.post(
        CHAT_URL,
        json={"message": message, "sid": sid, "tenant_slug": TENANT_SLUG},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("reply") or "").strip()


def get_customer_reply(conversation_history: list[dict]) -> str:
    """Use DeepSeek to generate the next customer message."""
    client = _deepseek_client()
    messages = [{"role": "system", "content": CUSTOMER_SYSTEM_PROMPT}]
    for turn in conversation_history:
        messages.append({"role": "user", "content": f"[Receptor]: {turn['receptionist']}"})
        messages.append({"role": "assistant", "content": turn['customer']})
    messages.append({"role": "user", "content": (
        "Kaj rečeš naslednje? Odgovori SAMO s sporočilom stranke, nič drugega. "
        "Bodi naravna in sproščena. Če si pripravljena rezervirati, povej to. "
        "Če nisi prepričana, oklevaj. Ne ponavljaj se."
    )})

    resp = client.chat.completions.create(
        model="deepseek-chat",
        temperature=0.9,
        messages=messages,
    )
    return resp.choices[0].message.content.strip()


def verify_data(sid: str):
    """Check what was persisted in PostgreSQL."""
    print("\n" + "=" * 60)
    print("VERIFYING PERSISTED DATA")
    print("=" * 60)

    import psycopg2
    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://ace_user:test_password_123@localhost:5433/ace_platform"))
    cur = conn.cursor()

    try:
        # 1. Lead
        cur.execute("SELECT id, sid, display_name, qualification_score, qualification_band, takeover_active, last_message_preview FROM leads WHERE sid = %s", (sid,))
        lead = cur.fetchone()
        if lead:
            print(f"\n🗄️  leads table:")
            print(f"   id={lead[0]}  sid={lead[1]}  name={lead[2]}  score={lead[3]}  band={lead[4]}  takeover={lead[5]}")
            print(f"   last_msg={lead[6][:80] if lead[6] else '(none)'}")

            # 2. Messages
            cur.execute("SELECT id, role, text FROM conversation_messages WHERE lead_id = %s ORDER BY created_at", (lead[0],))
            msgs = cur.fetchall()
            print(f"\n🗄️  conversation_messages — {len(msgs)} messages")
            for m in msgs:
                print(f"   [{m[1]}] {m[2][:100]}")
        else:
            print(f"\n❌ NO lead found for sid={sid}")

        # 3. Bookings (if any)
        cur.execute("SELECT id, service_name, booking_date, booking_time, price_eur, status FROM bookings WHERE organization_id = (SELECT id FROM organizations WHERE slug = 'demo') ORDER BY id DESC LIMIT 5")
        bookings = cur.fetchall()
        if bookings:
            print(f"\n🗄️  bookings — {len(bookings)} recent:")
            for b in bookings:
                print(f"   id={b[0]}  {b[1]}  {b[2]} {b[3]}  {b[4]}€  {b[5]}")
        else:
            print(f"\n🗄️  bookings — none")

    finally:
        cur.close()
        conn.close()


def run_conversation(sid: str, simple: bool = False, max_turns: int = 6):
    print("=" * 60)
    print("ACE SINGLE CONVERSATION TEST")
    print(f"SID: {sid}")
    print(f"Mode: {'simple (hardcoded)' if simple else 'LLM customer simulator (DeepSeek)'}")
    print(f"Backend: {CHAT_URL}")
    print("=" * 60)

    history = []
    turn = 0
    greeting = DEMOGRAPHICS["ime"] + ": Živjo!"

    while turn < max_turns:
        turn += 1

        if turn == 1:
            customer_msg = greeting
        elif simple:
            if turn - 2 < len(SIMPLE_MESSAGES):
                customer_msg = SIMPLE_MESSAGES[turn - 2]
            else:
                print(f"\n⏹️  No more hardcoded messages (turn {turn}/{max_turns})")
                break
        else:
            customer_msg = get_customer_reply(history)
            print(f"\n🤖 DeepSeek generated customer message...")

        print(f"\n── Turn {turn}/{max_turns} ──")
        print(f"👤 {DEMOGRAPHICS['ime']}: {customer_msg}")

        # Send to ACE
        response = send_chat(sid, customer_msg)
        print(f"🤖 Receptor: {response[:300]}{'...' if len(response) > 300 else ''}")

        history.append({"customer": customer_msg, "receptionist": response})

        # Check for ending conditions
        lower = response.lower()
        if any(phrase in lower for phrase in ["lep pozdrav", "nasvidenje", "adijo", "hvala lepa"]):
            print("\n🏁 Conversation appears to be ending.")
            break

        time.sleep(0.5)

    print(f"\n✅ Conversation complete — {turn} turns")
    return history


def main():
    parser = argparse.ArgumentParser(description="Test a single ACE conversation")
    parser.add_argument("--sid", default=None, help="Session ID (generated if not provided)")
    parser.add_argument("--simple", action="store_true", help="Use hardcoded messages instead of LLM")
    parser.add_argument("--max-turns", type=int, default=6, help="Maximum conversation turns")
    parser.add_argument("--verify", action="store_true", help="Verify persisted data after conversation")
    args = parser.parse_args()

    sid = args.sid or f"sim-{uuid.uuid4().hex[:8]}"

    # Check backend is up
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend reachable: {r.status_code}")
    except requests.ConnectionError:
        print(f"❌ Backend not reachable at {BASE_URL}")
        print("   Start with: uvicorn app.main:app --port 8000 --reload")
        sys.exit(1)

    # Check DeepSeek key
    if not args.simple and not DEEPSEEK_API_KEY:
        print("⚠️  DEEPSEEK_API_KEY not set. Falling back to --simple mode.")
        args.simple = True

    history = run_conversation(sid, simple=args.simple, max_turns=args.max_turns)

    # Summary
    print("\n" + "=" * 60)
    print("CONVERSATION SUMMARY")
    print("=" * 60)
    for i, turn in enumerate(history, 1):
        print(f"\nTurn {i}:")
        print(f"  👤 {turn['customer'][:120]}")
        print(f"  🤖 {turn['receptionist'][:120]}")

    if args.verify:
        verify_data(sid)
    else:
        print(f"\n💡 Run with --verify to check database persistence")
        print(f"   SID: {sid}")

    # Save to file for inspection
    out_path = Path(__file__).parent / f"test_conv_{sid}.json"
    out_path.write_text(json.dumps({
        "sid": sid,
        "turns": len(history),
        "history": history,
        "demographics": DEMOGRAPHICS,
    }, ensure_ascii=False, indent=2))
    print(f"\n📝 Conversation saved to: {out_path}")


if __name__ == "__main__":
    main()
