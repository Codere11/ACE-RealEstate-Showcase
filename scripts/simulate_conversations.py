#!/usr/bin/env python3 -u
"""
Orchestrator — runs 100 realistic conversations through the full ACE pipeline.

Each conversation:
  - Draws a fresh demographics card from the weighted sampler (no hardcoded profiles)
  - Customer Simulator (DeepSeek) plays the role based on that card
  - POST /chat hits the real ACE pipeline (LangGraph → tools → DB persist)
  - Side effects detected: bookings, payments, staff requests, add-ons, drop-offs
  - Outcomes are NOT predetermined — they emerge from how the conversation unfolds

Usage:
  python scripts/simulate_conversations.py              # fresh run, 100 convos
  python scripts/simulate_conversations.py --resume     # pick up where left off
  python scripts/simulate_conversations.py --total 30   # override count

Requires:
  - Backend running at http://localhost:8000
  - DEEPSEEK_API_KEY env var set
  - scripts/person_pool.json present
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

# Force unbuffered stdout — progress bar must show immediately
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

import requests
from openai import OpenAI

# ── Config ──
BASE_URL = os.getenv("ACE_BASE_URL", "http://localhost:8000")
CHAT_URL = f"{BASE_URL}/chat"
TENANT_SLUG = "demo"
MAX_TURNS = 10
TOTAL_CONVERSATIONS = 100
STATE_PATH = Path(__file__).parent / "sim_state.json"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    print("❌ DEEPSEEK_API_KEY not set. Export it and retry.")
    sys.exit(1)

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ── Import sampler ──
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.demographics import DemographicsSampler


# ═══════════════════════════════════════════════════════════
#  Customer Simulator prompt builder
# ═══════════════════════════════════════════════════════════

def _age_tone(age: int, bucket: str) -> str:
    """Vary speech style by age group."""
    if bucket == "18-24":
        return random.choice([
            "Si sproščen/a v izražanju. Uporabljaš pogovorni jezik, včasih kakšen angleški izraz ali sleng mlajše generacije ('ful', 'top', 'kul'). Pišeš kratke stavke brez pretiranega olepševanja.",
            "Govoriš zelo sproščeno, skoraj kot v SMS-sporočilih. Uporabljaš izraze kot 'huda stvar', 'to mi je všeč', 'ful dobr'. Ne kompliciraš.",
        ])
    elif bucket in ("25-34", "35-44"):
        return random.choice([
            "Govoriš naravno, umirjeno, poslovno-prijateljsko. Znaš postaviti direktno vprašanje, ampak si vljuden/a. Občasno uporabiš kakšen pogovorni izraz.",
            "Si praktičen/praktična. Sprašuješ konkretna vprašanja, ceniš dobre informacije, ampak ostajaš sproščen/a v tonu.",
        ])
    elif bucket == "45-54":
        return random.choice([
            "Govoriš zrelo, spoštljivo, a ne preveč formalno. Ceniš jasne odgovore. Včasih omeniš izkušnje iz preteklosti ('sem že bila pri vas', 'poznam salon').",
            "Si izkušen/a gostja kozmetičnih salonov. Govoriš samozavestno, veš kaj hočeš, ampak nisi nesramen/na.",
        ])
    else:  # 55+
        return random.choice([
            "Govoriš bolj tradicionalno slovensko, z občasnimi starinskimi izrazi ('kako pa to poteka', 'prosim povejte'). Ceniš oseben pristop in nisi vajen/a spletnega naročanja.",
            "Si starejša gospa/gospod. Govoriš umirjeno, spoštljivo. Mogoče malo oklevaš s spletno rezervacijo ker nisi najbolj vešč/a tehnologije.",
        ])


def _channel_tone(channel: str) -> str:
    """Vary behavior based on how they found the salon."""
    tones = {
        "Instagram": "Salon si odkril/a na Instagramu in všeč so ti njihove objave. Omeni to ('sem vas videla na Instagramu', 'všeč so mi vaši rezultati').",
        "priporočilo": "Salon ti je priporočil/a prijatelj/ica. Zaupaš jim že vnaprej. Omeni priporočilo ('prijateljica mi je rekla', 'so mi vas priporočili').",
        "Google": "Našel/našla si salon preko Googla. Si bolj raziskovalen/na — primerjaš, sprašuješ o rezultatih, mogoče pogledaš ocene.",
        "mimoidoči": "Šel/šla si mimo salona in te je zanimalo. Nisi še prepričan/a, sprašuješ osnovne stvari — 'kaj pa sploh delate', 'koliko stane'. Fizična bližina salona ti je pomembna.",
        "Facebook": "Salon si videl/a na Facebooku. Si bolj tradicionalen uporabnik družbenih omrežij. Govoriš preprosto, brez modernega slenga.",
    }
    return tones.get(channel, "")


def _customer_type_tone(ctype: str) -> str:
    if "nova" in ctype:
        return "Prvič si v stiku s tem salonom. Ničesar ne veš o njihovih storitvah razen tega kar ti receptor pove."
    return "Si vračajoča stranka — že si bil/a tukaj. Omeni prejšnji obisk, mogoče pohvali prejšnjo izkušnjo ('zadnjič je bilo super', 'spet bi rada k vam')."


def _budget_tone(budget: str) -> str:
    if "visoka" in budget:
        return random.choice([
            "Si zelo občutljiv/a na ceno. Sprašuješ o ceni takoj na začetku. Iščeš najboljšo vrednost za denar. Mogoče vprašaš za popust ali akcijo.",
            "Cena ti je ZELO pomembna. Primerjaš s konkurenco. Če se ti zdi predrago, boš to povedal/a direktno.",
        ])
    elif "premium" in budget or "nizka" in budget:
        return random.choice([
            "Cena ti ni pomembna — iščeš kvaliteto in vrhunsko izkušnjo. Pripravljen/a si plačati več za najboljše. Sprašuj po premium opcijah.",
            "Denar ni problem. Hočeš najboljšo obravnavo, najboljše izdelke, največ časa. Vprašaj 'kaj je najboljše kar imate'.",
        ])
    else:  # srednja
        return random.choice([
            "Cena ti je pomembna, ampak nisi obseden/a s tem. Si pripravljen/a plačati pošteno ceno za dobro storitev.",
            "Zanima te razmerje cena/kakovost. Ne boš izbral/a najdražje opcije, ampak tudi ne boš šparal/a na račun kvalitete.",
        ])


def _disposition_tone(disp: str) -> str:
    if "samo brskam" in disp:
        extras = [
            "Nisi prepričan/a če boš sploh kaj rezerviral/a. Ampak če te receptor prepriča, si pripravljen/a spremeniti mnenje.",
            "Bolj raziskuješ trg. Rezervacija ni tvoj primarni cilj zdaj, ampak če najdeš nekaj zanimivega, boš mogoče rezerviral/a.",
        ]
    elif "raziskujem" in disp or "načrtujem" in disp:
        extras = [
            "Resno razmišljaš o rezervaciji, ampak še zbiraš informacije. Sprašuj podrobna vprašanja o postopkih, trajanju, rezultatih.",
            "Si v fazi odločanja. Rabiš dobre argumente, da se odločiš. Primerjaš storitve med sabo.",
        ]
    elif "pripravljen" in disp or "pripravljena" in disp:
        extras = [
            "Si pripravljen/a rezervirati zdaj. Aktivno sprašuj po terminih in kako poteka rezervacija.",
            "Veš da hočeš rezervirati — samo še termin in ceno rabiš. Bodi direkten/na — 'kako pa rezerviram', 'imate kaj prosto'.",
        ]
    else:  # vem kaj hočem
        extras = [
            "Točno veš kaj hočeš. Bodi samozavesten/na, skoraj zahteven/na. Ne zapravljaj časa z osnovnimi informacijami.",
            "Si odločen/a. Povej direktno kaj želiš, ne čakaj da receptor ugiba. 'Rabim nego obraza, najboljšo ki jo imate.'",
        ]
    return random.choice(extras)


def _quirk_instruction(quirk: str) -> str:
    if quirk == "nobena":
        return ""
    if quirk == "osebje":
        return "Če ti receptor ne bo znal odgovoriti na vprašanje, ali če bo preveč 'robotski', zahtevaj pogovor z živim osebjem. Reci 'a lahko dobim osebje' ali podobno."
    if quirk == "plačilo":
        return "Nervozen/a si glede spletnega plačevanja. Ko pride do plačila, oklevaj — sprašuj o varnosti, ali lahko plačaš z gotovino na licu mesta, ali je spletno plačilo varno."
    if "VIP" in quirk or "zahtevna" in quirk:
        return "Si VIP stranka — zahtevna, hočeš najboljše. Sprašuj po premium tretmajih, najboljših terminih, specifičnih kozmetičarkah. Če ti kaj ne ustreza, boš to jasno povedal/a."
    if "no-show" in quirk or "negotov" in quirk:
        return "Nisi najbolj zanesljiv/a. Mogoče boš rezerviral/a termin, ampak boš potem okleval/a, spraševal/a če se da prestaviti, ali povedal/a da 'bom še premislil/a' tudi po rezervaciji."
    return ""


def build_system_prompt(profile: dict) -> str:
    """
    Build a rich, varied system prompt for the Customer Simulator.
    Age, gender, channel, budget, disposition, and quirks all shape the persona.
    """
    age_bucket = profile.get("age_bucket", "30")
    gender = profile.get("spol", "ženska")
    a = "a" if gender == "ženska" else ""

    parts = [
        f"Ti si {profile['ime']}, {profile['starost']}-letn{a} {gender}.",
        _age_tone(profile["starost"], age_bucket),
        f"Našel/našl{a} si salon preko: {profile['kanal']}.",
        _channel_tone(profile["kanal"]),
        f"Status: {profile['nov_ali_vracajoc']}.",
        _customer_type_tone(profile["nov_ali_vracajoc"]),
        f"Zanima te: {profile['zanima_jo']}.",
        f"Občutljivost na ceno: {profile['obcutljivost_na_ceno']}.",
        _budget_tone(profile["obcutljivost_na_ceno"]),
        f"Dispozicija: {profile['dispozicija']}.",
        _disposition_tone(profile["dispozicija"]),
    ]

    quirk = profile.get("posebnosti", "nobena")
    quirk_inst = _quirk_instruction(quirk)
    if quirk_inst:
        parts.append(quirk_inst)

    parts.extend([
        "",
        "POMEMBNA NAVODILA:",
        "- Govoriš naravno sproščeno slovenščino z občasnimi pogovornimi izrazi.",
        "- Ne veš ničesar o salonu razen tega kar ti receptor pove.",
        "- Odločitev o rezervaciji sprejmeš GLEDE NA POTEK POGOVORA.",
        "  Nisi programiran/a da rezerviraš ali da ne rezerviraš.",
        "  Če te receptor prepriča, rezerviraj. Če ne, pojdi stran.",
        "- Če si vračajoč/a stranka, se tega spomni v pogovoru.",
        "- Bodi naraven/naravna: včasih oklevaj, včasih bodi navdušen/a.",
        "- Uporabljaj VIKANJE (vi, vas) ko govoriš z receptorjem.",
        "- Vsaka oseba je edinstvena — ne ponavljaj istih fraz kot drugi.",
    ])

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
#  Customer Simulator — DeepSeek call
# ═══════════════════════════════════════════════════════════

def customer_reply(profile: dict, history: list[dict]) -> str:
    """Ask DeepSeek what the customer says next, given full persona + history."""
    msgs = [{"role": "system", "content": build_system_prompt(profile)}]

    for turn in history:
        msgs.append({"role": "user", "content": f"[Receptor]: {turn['receptionist']}"})
        msgs.append({"role": "assistant", "content": turn['customer']})

    msgs.append({
        "role": "user",
        "content": (
            "Kaj rečeš naslednje? Odgovori SAMO s sporočilom stranke, nič drugega. "
            "Bodi naraven/naravna in v skladu s svojo osebnostjo. "
            "Če si pripravljen/a rezervirati — to povej. Če oklevaš — oklevaj. "
            "Če želiš oditi — se poslovi."
        ),
    })

    for attempt in range(3):
        try:
            resp = deepseek.chat.completions.create(
                model="deepseek-chat",
                temperature=0.85 + random.random() * 0.1,  # 0.85–0.95 for genuine variability
                messages=msgs,
                timeout=30,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt == 2:
                raise
            print(f"   ⚠️  DeepSeek retry {attempt+1}/3: {e}")
            time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
    return ""  # unreachable


# ═══════════════════════════════════════════════════════════
#  ACE chat interface
# ═══════════════════════════════════════════════════════════

def send_chat(sid: str, message: str) -> str:
    for attempt in range(3):
        try:
            resp = requests.post(CHAT_URL, json={
                "message": message, "sid": sid, "tenant_slug": TENANT_SLUG,
            }, timeout=60)
            resp.raise_for_status()
            return (resp.json().get("reply") or "").strip()
        except Exception as e:
            if attempt == 2:
                raise
            print(f"   ⚠️  Chat retry {attempt+1}/3: {e}")
            time.sleep(2 ** attempt)
    return ""  # unreachable


def extract_payment_token(reply: str) -> str | None:
    match = re.search(r'http://localhost:8000/pay/([^\s\)\.]+)', reply)
    return match.group(1) if match else None


def complete_payment(token: str) -> bool:
    try:
        r = requests.post(f"http://localhost:8000/pay/{token}/complete", timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def is_goodbye(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "adijo", "nasvidenje", "lep pozdrav", "hvala lepa",
        "se vidimo", "lep dan", "hvala za vse", "bom še razmislil",
        "bom še razmislila", "bom premislil", "bom premislila",
        "se še oglasim", "vam sporočim",
    ])


def detect_add_ons(text: str) -> int:
    """Count how many add-on references appear in the reply."""
    addon_keywords = [
        "kolagenska maska", "limfna drenaža", "LED terapija",
        "hialuronski serum", "pomirjevalna krema", "očesni tretma",
        "encimski piling", "dopolnitev", "dodatek",
    ]
    lower = text.lower()
    return sum(1 for kw in addon_keywords if kw in lower)


# ═══════════════════════════════════════════════════════════
#  Run one conversation
# ═══════════════════════════════════════════════════════════

def run_conversation(index: int, profile: dict) -> dict:
    """
    Run one full conversation. Customer is powered by DeepSeek with the
    demographics profile. ACE receptionist is the real system at /chat.
    """
    sid = f"sim-{index:03d}"
    name = profile["ime"]

    history: list[dict] = []
    booked = False
    paid = False
    staff_requested = False
    add_ons_mentioned = 0
    payment_attempted = False
    payment_succeeded = False
    dropped_off = False
    outcome = "unknown"

    # Variable first message — don't always say the same thing
    greetings = [
        f"Živjo!",
        f"Dober dan!",
        f"Zdravo!",
        f"Pozdravljeni!",
        f"Živjo, zanima me ena stvar...",
        f"Dober dan, sem prvič tukaj...",
        f"Hello! A imate kaj prosto?",
    ]

    for turn in range(1, MAX_TURNS + 1):
        if turn == 1:
            customer_msg = random.choice(greetings)
        else:
            customer_msg = customer_reply(profile, history)

        try:
            response = send_chat(sid, customer_msg)
        except Exception as e:
            print(f"\n   ⚠️  API error on turn {turn}: {e}")
            dropped_off = True
            outcome = "error"
            break

        history.append({"customer": customer_msg, "receptionist": response})

        # ── Side effect detection ──

        # Payment
        if not paid:
            token = extract_payment_token(response)
            if token:
                payment_attempted = True
                if complete_payment(token):
                    payment_succeeded = True
                    paid = True
                else:
                    payment_succeeded = False

        # Booking confirmed (check for any booking confirmation language)
        if not booked:
            lower = response.lower()
            booking_signals = [
                "potrjen", "rezerviran", "rezervacija", "vas pričakujemo",
                "uspešno rezervir", "termin je vaš", "ste rezervirali",
            ]
            has_signal = any(s in lower for s in booking_signals)
            has_detail = any(d in lower for d in ["termin", "datum", "ura", "obisk"])
            if has_signal and has_detail:
                booked = True
                outcome = "booked"

        # Staff request
        if not staff_requested:
            if "osebje" in response.lower() and ("zahteva" in response.lower() or "zahtev" in response.lower() or "poklicati" in response.lower()):
                staff_requested = True

        # Add-ons
        add_ons_mentioned += detect_add_ons(response)

        # Drop-off (customer says goodbye or loses interest)
        if is_goodbye(customer_msg):
            if not booked:
                dropped_off = True
                outcome = "dropped_off"
            break

        if is_goodbye(response):
            if not booked:
                dropped_off = True
                if outcome == "unknown":
                    outcome = "dropped_off"
            break

        time.sleep(0.25)

    # If we hit max turns without booking or goodbye
    if outcome == "unknown":
        outcome = "dropped_off" if not booked else "booked"
        if not booked:
            dropped_off = True

    return {
        "sid": sid,
        "index": index,
        "ime": name,
        "starost": profile["starost"],
        "spol": profile["spol"],
        "kanal": profile["kanal"],
        "zanima_jo": profile["zanima_jo"],
        "obcutljivost_na_ceno": profile["obcutljivost_na_ceno"],
        "dispozicija": profile["dispozicija"],
        "posebnosti": profile["posebnosti"],
        "nov_ali_vracajoc": profile["nov_ali_vracajoc"],
        "age_bucket": profile.get("age_bucket", ""),
        "turns": len(history),
        "outcome": outcome,
        "booked": booked,
        "dropped_off": dropped_off,
        "paid": paid,
        "payment_attempted": payment_attempted,
        "payment_succeeded": payment_succeeded,
        "staff_requested": staff_requested,
        "add_ons_mentioned": add_ons_mentioned,
        "history": history,
    }


# ═══════════════════════════════════════════════════════════
#  Progress display
# ═══════════════════════════════════════════════════════════

def progress_bar(current: int, total: int, width: int = 30) -> str:
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = current / total * 100
    return f"[{bar}] {current}/{total} ({pct:.0f}%)"


def format_result_marker(result: dict) -> str:
    """Single-character marker for the result line."""
    if result["paid"]:
        return "💳"
    if result["booked"]:
        return "✅"
    if result["dropped_off"]:
        return "❌"
    return "❓"


def print_compact_result(result: dict):
    """One-line result per conversation."""
    marker = format_result_marker(result)
    name = result["ime"]
    turns = result["turns"]
    disp = result["dispozicija"][:30]
    addons = f" +{result['add_ons_mentioned']}" if result["add_ons_mentioned"] else ""
    staff = " 👥" if result["staff_requested"] else ""
    paid_str = " PAID" if result["paid"] else ""
    print(f" {marker} {name:<12s} {turns}t {disp}{addons}{staff}{paid_str}")


# ═══════════════════════════════════════════════════════════
#  State management
# ═══════════════════════════════════════════════════════════

def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"completed": 0, "results": [], "counts": {}}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════

def print_summary(results: list[dict], sampler: DemographicsSampler):
    n = len(results)
    booked = sum(1 for r in results if r["booked"])
    dropped = sum(1 for r in results if r["dropped_off"])
    paid = sum(1 for r in results if r["paid"])
    staff = sum(1 for r in results if r["staff_requested"])
    addons_total = sum(r["add_ons_mentioned"] for r in results)
    payment_attempts = sum(1 for r in results if r["payment_attempted"])
    avg_turns = sum(r["turns"] for r in results) / n if n else 0

    print(f"\n{'═' * 60}")
    print("SIMULATION COMPLETE")
    print(f"{'═' * 60}")
    print(f"  Total conversations:     {n}")
    print(f"  Booked:                  {booked} ({booked/n*100:.0f}%)" if n else "  Booked: 0")
    print(f"  Dropped off:             {dropped} ({dropped/n*100:.0f}%)" if n else "  Dropped: 0")
    print(f"  Paid:                    {paid} ({paid/n*100:.0f}%)" if n else "  Paid: 0")
    print(f"  Payment attempts:        {payment_attempts}")
    print(f"  Staff requested:         {staff}")
    print(f"  Add-ons mentioned:       {addons_total}")
    print(f"  Avg turns:               {avg_turns:.1f}")

    # Breakdown by disposition
    print(f"\n  OUTCOME BY DISPOSITION:")
    by_disp: dict[str, dict] = {}
    for r in results:
        d = r["dispozicija"][:30]
        if d not in by_disp:
            by_disp[d] = {"total": 0, "booked": 0, "dropped": 0}
        by_disp[d]["total"] += 1
        if r["booked"]:
            by_disp[d]["booked"] += 1
        if r["dropped_off"]:
            by_disp[d]["dropped"] += 1
    for d, c in sorted(by_disp.items()):
        print(f"    {d:<32s} total={c['total']:2d}  booked={c['booked']:2d}  dropped={c['dropped']:2d}")

    # Breakdown by quirk
    print(f"\n  OUTCOME BY QUIRK:")
    by_quirk: dict[str, dict] = {}
    for r in results:
        q = r["posebnosti"]
        if q not in by_quirk:
            by_quirk[q] = {"total": 0, "booked": 0, "dropped": 0, "staff": 0, "paid": 0}
        by_quirk[q]["total"] += 1
        if r["booked"]:
            by_quirk[q]["booked"] += 1
        if r["dropped_off"]:
            by_quirk[q]["dropped"] += 1
        if r["staff_requested"]:
            by_quirk[q]["staff"] += 1
        if r["paid"]:
            by_quirk[q]["paid"] += 1
    for q, c in sorted(by_quirk.items()):
        print(f"    {q:<20s} total={c['total']:2d}  booked={c['booked']:2d}  dropped={c['dropped']:2d}  staff={c['staff']:2d}  paid={c['paid']:2d}")

    # Sampler distribution report
    print(sampler.summary())

    print(f"\n  State saved to: {STATE_PATH}")


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ACE Conversation Simulator — 100 realistic conversations")
    parser.add_argument("--resume", action="store_true", help="Resume from saved state")
    parser.add_argument("--total", type=int, default=TOTAL_CONVERSATIONS, help=f"Total conversations to run (default: {TOTAL_CONVERSATIONS})")
    args = parser.parse_args()

    # ── Health check ──
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Backend reachable: {r.status_code}")
    except Exception:
        print(f"❌ Backend not reachable at {BASE_URL}")
        sys.exit(1)

    # ── Initialize sampler ──
    sampler = DemographicsSampler()

    # ── Load or create state ──
    if args.resume:
        state = load_state()
        # Re-feed past results so distribution trackers are current
        sampler.restore_from_results(state.get("results", []))
    else:
        state = {"completed": 0, "results": [], "counts": {}}
    start = state["completed"]
    total = args.total

    print(f"\n{'═' * 60}")
    print(f"ACE CONVERSATION SIMULATOR")
    print(f"{'═' * 60}")
    print(f"  Conversations:   {total}")
    print(f"  Starting at:     {start + 1}")
    print(f"  Mode:            {'resume' if args.resume else 'fresh'}")
    print(f"  Customer LLM:    DeepSeek (deepseek-chat, temp=0.85–0.95)")
    print(f"  ACE Backend:     {BASE_URL}")
    if start > 0:
        print(f"  Resuming — {start} already completed, {total - start} remaining")
    print(f"{'═' * 60}\n")

    if start >= total:
        print("✅ All conversations already completed.")
        print_summary(state["results"], sampler)
        return

    # ── Run loop ──
    for i in range(start, total):
        # Progress header
        print(f"\n{progress_bar(i + 1, total)}", flush=True)
        print(f"{'─' * 60}", flush=True)

        # Draw fresh demographics
        profile = sampler.draw()

        # Run conversation
        result = run_conversation(i, profile)

        # Compact result
        print_compact_result(result)
        sys.stdout.flush()

        # Track
        state["results"].append(result)
        state["completed"] = i + 1
        save_state(state)

    # ── Final summary ──
    print_summary(state["results"], sampler)


if __name__ == "__main__":
    main()
