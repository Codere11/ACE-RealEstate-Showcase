# Analize — Business Intelligence Tab

## Goal

A dedicated LangChain/LangGraph-powered analysis tab in the org dashboard that queries real conversation, lead, and booking data to produce actionable, no-fluff business insights — without manual data export or external tools.

> **The data is real — not mocked, not fabricated.** Every simulated customer conversation hits the actual ACE pipeline: `POST /chat` → LangGraph → tool calls → PostgreSQL. The leads, messages, bookings, and events land in the same database the org dashboard reads. Open the dashboard after a simulation run and you see exactly what a real salon owner would see: real-looking leads, real conversation threads, real calendar slots filling up.
>
> When the Analize tab later queries this data with its AI (finding funnel leaks, drop-off points, upsell opportunities), it's analyzing the *actual system's performance*. The leaks it finds are real leaks. The upsell opportunities it surfaces are real gaps the bot left on the table. No simulated analytics on simulated data — real analytics on real system output.

---

## Tab Design

### Flow

The Analize tab has three phases, top to bottom:

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1 — INTENT                                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  "Kaj želite izvedeti?"                                ││
│  │  ┌─────────────────────────────────────────────────────┐││
│  │  │  (prosto besedilo — manager napiše vprašanje)      │││
│  │  │  npr: "Kje izgubljam stranke? Kdo kupuje           │││
│  │  │   dodatke? Primerjaj uspešne in neuspešne          │││
│  │  │   pogovore."                                       │││
│  │  └─────────────────────────────────────────────────────┘││
│  │                                             [Pripravi]  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2 — PROCESSING (prikaže se po kliku "Pripravi")     │
│                                                             │
│  AI enega za drugim prebere vseh 100 pogovorov in          │
│  vsakemu prilepi oznake:                                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  ████████████████████░░░░░░░  67 / 100                  ││
│  │                                                         ││
│  │  ✅ Mojca     → označeno: brskalka, cenovno             ││
│  │                  občutljiva, padla pri plačilu          ││
│  │  ✅ Tilen     → označeno: pripravljen, hitra            ││
│  │                  rezervacija, brez dodatkov             ││
│  │  ⏳ Maja      → berem...                                ││
│  │  ⏸️  Peter     → čaka v vrsti                           ││
│  │  ...                                                    ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  AI zgradi indeks: funnel stopnje, segmenti, sentiment,    │
│  točke osipa, priložnosti za upsell, neodgovorjena         │
│  vprašanja, primerjave med uspešnimi/neuspešnimi.          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3 — DISCUSSION (chatbot)                             │
│                                                             │
│  Manager v prostem jeziku sprašuje o označenih             │
│  podatkih. AI odgovarja samo na podlagi label.             │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  🧑 » Kje največ ljudi odpade?                         ││
│  │  🤖 » 38 ljudi je pozdravilo in niso več               ││
│  │  │   odgovorili. 22 jih je vprašalo za ceno            ││
│  │  │   in nato odšlo — večinoma pri negi obraza          ││
│  │  │   (45€). To je 60 % vseh osipov.                    ││
│  │  │                                                     ││
│  │  │   Funnel:                                           ││
│  │  │   100 pozdravljenih                                 ││
│  │  │   ████████████████████████████████████████          ││
│  │  │   62 vprašalo po storitvah                          ││
│  │  │   ██████████████████████████                        ││
│  │  │   34 vprašalo za termin                             ││
│  │  │   ██████████████                                    ││
│  │  │   29 rezerviralo                                    ││
│  │  │   ████████████                                      ││
│  │  │                                                     ││
│  │  ─────────────────────────────────────────────         ││
│  │  🧑 » Primerjaj tiste ki so rezervirali s             ││
│  │  │   tistimi ki so odšli pri ceni.                     ││
│  │  🤖 » Rezervirali: povprečno 2.1 vprašanja            ││
│  │  │   pred rezervacijo, večinoma Instagram in           ││
│  │  │   priporočila.                                      ││
│  │  │   Odšli pri ceni: povprečno 4.3 vprašanja,         ││
│  │  │   večinoma Google in mimoidoči. 8 od 22            ││
│  │  │   je vprašalo za popust. Bot nikoli ni             ││
│  │  │   ponudil alternativne cenejše storitve.           ││
│  │  ─────────────────────────────────────────────         ││
│  │  🧑 » Kaj bi moral spremeniti?                        ││
│  │  🤖 » 1. Ko stranka vpraša za ceno nege               ││
│  │  │   obraza (45€), bot naj takoj omeni tudi           ││
│  │  │   cenejšo alternativo — masko obraza (30€).       ││
│  │  │   2. Google/mimoidoči reagirajo na ceno —          ││
│  │  │   bot naj pri teh kanalih vodi s ceno.             ││
│  │  │   3. 14 ljudi je omenilo dodatke, samo 3           ││
│  │  │   so jih kupili — bot jih omenja prepozno.         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  (novo vprašanje...)                         [Pošlji]  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Key design decisions

**Phase 1 — Free-form intent.** Manager ne izbira iz dropdowna. Napiše v naravnem jeziku kaj ga zanima. To vprašanje gre v system prompt faze 2 in vpliva na to KATERE oznake AI prilepi vsakemu pogovoru. Če vpraša "kje izgubljam stranke", AI pri vsakem pogovoru označi točko osipa. Če vpraša "kdo kupuje dodatke", AI označi upsell priložnosti. Če ne napiše ničesar, AI uporabi default oznake (funnel stopnja, segment, sentiment, osip, upsell flag).

**Phase 2 — Konverzacijsko označevanje (labelling).** AI zaporedno bere vsak pogovor (vse replike: uporabnik + receptor) in mu prilepi strukturirane oznake. To NI en LLM klic z vsemi 100 pogovori naenkrat — to bi ubilo context window in kvaliteto. Namesto tega: en LLM klic na pogovor (100 klicev), vsak dobi isti system prompt (z vprašanjem managerja iz faze 1) + ta en pogovor. Rezultat vsakega klica je JSON z oznakami. Vsi JSON-i se shranijo v spomin (backend session state). Teče zaporedno — počasneje, ampak natančno, poceni, in z indikatorjem napredka (67/100).

**Phase 3 — Chatbot nad označenimi podatki.** Ko so vsi pogovori označeni, se prikaže chat vmesnik. Manager v prostem jeziku sprašuje. AI (en system prompt z vsemi oznakami + funnel strukturo + originalnim vprašanjem) odgovarja. Manager lahko drill-down: "pokaži mi vse ki so odpadli pri plačilu", "primerjaj Instagram z Googlom", "kaj je skupnega uspešnim pogovorom". AI ima na voljo samo označene podatke — ne bere ponovno surovih pogovorov.

**Zakaj ne vse naenkrat?** Če bi poslal vseh 100 pogovorov v en LLM klic, bi:
- Presegel context window (100 × 6 sporočil × ~100 besed = ~60k besed)
- Izgubil natančnost (LLM ne more hkrati analizirati 100 ločenih pogovorov natančno)
- Plačal več (velik prompt = več tokenov)

Zaporedno označevanje je počasnejše (~30 sekund za 100 pogovorov pri DeepSeek hitrosti) ampak natančno in poceni. Indikator napredka naredi čakanje sprejemljivo.

### Backend architecture

```
POST /api/organizations/{org_id}/analize/prepare
  Body: { "question": "kje izgubljam stranke?" }
  → Zažene označevanje vseh pogovorov enega za drugim
  → Vrne { "job_id": "abc123", "total": 100 }

GET /api/organizations/{org_id}/analize/prepare/{job_id}/progress
  → Server-Sent Events ali polling: vrne trenutni napredek
  → { "done": 67, "total": 100, "current": "Mojca", "labels": [...] }

POST /api/organizations/{org_id}/analize/chat
  Body: { "question": "primerjaj uspešne in neuspešne", "job_id": "abc123" }
  → AI odgovori na podlagi vseh label iz joba
  → Vrne { "reply": "..." }

GET /api/organizations/{org_id}/analize/prepare/{job_id}/labels
  → Vrne vse oznake za vse pogovore (za cache / ponovno uporabo)
```

### Oznake, ki jih AI prilepi vsakemu pogovoru (primer)

```json
{
  "sid": "sim-000",
  "ime": "Mojca",
  "funnel_stopnja": "vprašala za ceno — nato odšla",
  "funnel_koraki": ["pozdrav", "vprašala za storitve", "vprašala za ceno", "odšla"],
  "segment": "cenovno občutljiva brskalka",
  "sentiment": "nevtralen, na koncu razočaran",
  "osip_točka": "cena nege obraza (45€) — ni dobila cenejše alternative",
  "upsell_priloznost": false,
  "upsell_detalji": null,
  "kljucni_trenutek": "Ko je bot povedal ceno 45€ ...",
  "kaj_bi_lahko_bilo_bolje": "Takoj ponuditi cenejšo alternativo.",
  "je_rezerviral": false,
  "je_placal": false,
  "dodatki_kupljeni": [],
  "trajanje_pogovora": "5 izmenjav"
}
```

---

## End-State Vision
## End-State Vision

The Analize tab is a **left-rail chat interface**. On the left: a list of AI experts and customer personas. Click one, and you're in a WhatsApp-style DM with them. No dashboards, no dropdowns, no cards. Just conversations with AI people who know your data.

```
┌────────────────────┬───────────────────────────────────────────────┐
│  ANALIZE           │                                               │
│                    │  ┌─────────────────────────────────────────┐  │
│  💼 Poslovni       │  │  🧑 Ti » Kako gre ta teden?            │  │
│     svetovalec    │  │  🤖 » 29 rezervacij, 1716€.             │  │
│                    │  │  │  18% zasedenost. 38 ghostov po      │  │
│  📣 Marketingar    │  │  │  pozdravu. Kontaktni loop vas je    │  │
│                    │  │  │  stal ~€350.                        │  │
│  👤 Cenovni lovec  │  │  │                                       │  │
│                    │  │  │  📊 Funnel                            │  │
│  👤 Instagram      │  │  │  100 ██████████████████████████████  │  │
│     brskalka      │  │  │   62 █████████████████████           │  │
│                    │  │  │   35 ████████████                   │  │
│  👤 VIP zahtevnež  │  │  │   29 ███████████  ✅                │  │
│                    │  │  │                                       │  │
│                    │  │  🧑 Ti » Zakaj jih 38 odpade?          │  │
│                    │  │  🤖 » 9 iskalo nohte, 4 masažo.        │  │
│                    │  │  │  Ne nudimo tega. Predlog: cross-    │  │
│                    │  │  │  sell na obrazne storitve.          │  │
│                    │  │  │  Vpliv: ●●●◐○ Trud: ●○○○○          │  │
│                    │  └─────────────────────────────────────────┘  │
│                    │  ┌─────────────────────────────────────────┐  │
│                    │  │  Napiši sporočilo...                   │  │
│                    │  └─────────────────────────────────────────┘  │
└────────────────────┴───────────────────────────────────────────────┘
```

### Left sidebar — AI people you chat with

**💼 Poslovni svetovalec (Business Advisor)**
The main thread. Has access to all labeled conversations, bookings, and funnel stats. Does SWOT analysis, funnel breakdowns, copywriting critique on the bot's messages, sales skills audit, objection handling playbook, and practical tips ranked by Impact/Effort coefficient (● = high, ○ = low). Answers any business question in natural language, backed by your data.

*Example questions: "Kaj je največji problem ta teden?", "Primerjaj uspešne in neuspešne pogovore.", "Kako izboljšati upsell?", "SWOT analiza."*

**📣 Marketingar (Marketing Expert)**
A separate AI persona focused on positioning, messaging, and conversion. Reads the bot's language and critiques it as a copywriter would. Suggests A/B test ideas for opening messages, upsell phrasing, objection responses. Knows which customer segments respond to which language. Can generate alternative versions of bot messages and predict which would convert better.

*Example questions: "Ali je moj uvodni pozdrav preveč generičen?", "Napiši 3 verzije odgovora na ugovor cene.", "Kateri segment najbolje reagira na besedo 'premium'?"*

**What a marketing pro actually does with Marketingar:**

**Conversion copy analysis** — not just "bot said this" but per-sentence close rates. "Ta stavek 'Razumem vaš pomislek, vendar so cene fiksne' ima 3% close rate. Ta drugi 'Imamo ugodnejšo alternativo — masko za 30€' ima 18%." The marketing guy finds the winning language in the data.

**Funnel by segment** — not aggregate numbers. "Instagram: 15% konverzija. Google: 8%. Priporočila: 40%. Facebook: 5%." Channel decisions get made from this.

**A/B test sandbox** — marketing guy types a new opening message. Marketingar simulates how each customer persona (Cenovni lovec, IG brskalka, VIP) would react, then gives a predicted close rate. "Nova verzija: predvidena 34% (trenutna: 29%). Cenovni lovec bo še vedno ugovarjal, ampak ujel boš več IG brskalk."

**Customer journey mapping** — per persona, exactly where each type drops. "Cenovni lovec: 70% osip pri ceni. IG brskalka: 50% osip pri prvem pozdravu. VIP: 0% osip — vsi rezervirajo." This tells the marketer WHERE to focus, not just THAT there's a problem.

**Language audit** — specific word-level critique. "Uporabil si besedo 'fiksna cena' 43-krat. To je negativni okvir. Zamenjaj z 'vključeno v ceno' — isti pomen, boljša percepcija." Or: "Bot se opravičuje 3-krat na pogovor. Preveč. Bodi bolj direkten."

**Before/after tracking** — Monday they change the contact-gathering message. Friday Marketingar reports: "Pred spremembo: 22% close rate. Po spremembi: 31%. 📈 Graf prilagam." Proof that their work moved the needle.

**👤 Cenovni lovec (Price Hunter)**
A stereotypical customer persona. Fed with all conversations where price objections killed the deal. You talk to it like a real bargain-hunting customer. It fires back with actual objections from your dataset. Use it to test new pricing strategies, practice downgrade offers, or see how your bot handles the "tam čez cesto je ceneje" conversation.

*Example: You type "Imamo 10% popust za prvi obisk" → Persona: "10%? To je še vedno 54€ namesto 60€. Tam čez cesto dobim za 45€. Kaj je boljšega pri vas?"*

**👤 Instagram brskalka (IG Browser)**
Stereotype: came from Instagram, loves the visuals, is curious but not committed. Fed with all Instagram-channel conversations that didn't book. Use it to understand why visual-first customers browse but don't buy, and to test messaging that converts curiosity into commitment.

**👤 VIP zahtevnež (VIP Demander)**
Stereotype: "Samo najboljše kar imate. Cena ni pomembna." Fed with all premium-buyer and VIP-quirk conversations. Tests luxury positioning, package offers, and specific staff requests. Shows you where your premium pitch falls flat.

### What each AI person can do

| Persona | Zna narediti |
|---|---|
| 💼 Poslovni svetovalec | SWOT, funnel, sales audit, objection playbook, Impact/Effort tips, "kaj stane največ", primerjave |
| 📣 Marketingar | Konverzijska analiza per stavek, funnel po segmentih, A/B peskovnik s simulacijo, jezikovni audit, before/after tracking |
| 👤 Cenovni lovec | Simulira pogajanje o ceni, testira nove popuste, pokaže kje bot izgubi pri ceni |
| 👤 IG brskalka | Simulira vizualno prvo izkušnjo, testira premium upsell za browsers |
| 👤 VIP zahtevnež | Simulira zahtevno stranko, testira paketne ponudbe, testira "najboljše kar imate" flow |

### Key principle: You talk to AI people, not to a dashboard

**For the owner:** Open the tab, click "Poslovni svetovalec," type "Kako gre?" The AI reads the data and replies with numbers, graphs, and what it's costing them. They don't explore — they ask and get told.

**For the marketing pro:** The tab is a workbench. They ask Marketingar for a language audit. They A/B test a new opening message against the Cenovni lovec persona. They pull a funnel-by-segment report. They change the bot's messaging and track the before/after. The personas aren't gimmicks — they're testing infrastructure.

Same data, two users, two completely different workflows. The chat interface is the constant.

---


The demo salon needs to feel real before analysis can be meaningful. Three bare services won't create interesting data. We need:

- **3 base services** (Nega obraza, Maska obraza, Čiščenje obraza)
- **3 add-ons per service** (e.g. kolagenska maska +15€, limfna drenaža +20€, LED terapija +10€) — these create upsell conversations the AI must handle
- **1 premium service** (e.g. "Royal nega obraza" 90min/95€) — some customers ask for "the best you have"
- **Dummy business contact**: phone `040 123 456`, email `info@lepota-sprostitev.si` — the AI references these when staff is unavailable or salon is closed
- **Customer demographics** — grounded in what a real Slovenian cosmetic salon sees. Sampled per conversation, never predetermined outcomes:

| Dimension | Distribution |
|-----------|-------------|
| Age | 25-34 (35%), 35-44 (30%), 18-24 (15%), 45-54 (12%), 55+ (8%) |
| Gender | Women (~92%), Men (~8%) |
| New vs. returning | New leads (60%), Existing clients (40%) |
| Service interest | Facial treatments (30%), Massage (25%), Hair removal (20%), Nails (15%), Permanent makeup (10%) |
| Source channel | Instagram (35%), Referral (25%), Google (20%), Walk-by (15%), Facebook (5%) |
| Budget sensitivity | Medium (50%), High — price-conscious (30%), Low — premium buyer (20%) |
| Booking disposition | Just browsing / curious (40%), Researching/planning (35%), Eager to book (25%) |
| Behavior quirks | None (70%), Might request staff (10%), Payment anxiety (10%), VIP/demanding (5%), Flaky/no-show tendency (5%) |

> Outcomes (booked, dropped, add-ons purchased) are NOT predetermined. They emerge from how the conversation actually unfolds. The demographics and disposition set the starting tone — a "just browsing" customer might book if the bot impresses them, and an "eager to book" customer might bail if the bot fumbles.

## Demo data purpose and setup

A Python script (`scripts/populate_demo.py`) that generates structured, realistic traffic through the system:

- Each "customer" has demographics sampled from the distributions above — age, channel, budget sensitivity, initial booking disposition, and any behavior quirks
- The script sends actual POST /chat requests (same API as the real visitor SPA), so the full pipeline runs: classification → tool calls → auto-book → DB persistence
- Conversations flow naturally — whether a customer books, drops off, requests staff, or buys add-ons is determined by the LLM playing the role, not by a script. An "eager" customer might still leave if the bot fails; a "curious" browser might end up booking if the bot is persuasive.
- Bookings land in the calendar only when the conversation genuinely reaches that point
- The calendar fills organically across multiple days — no pre-allocated slots. The simulator picks real available slots through the normal booking flow.
- Leads appear in the dashboard with varied statuses and staff-requested flags
- Some "customers" interact over multiple days (return visitors with conversation history)
- Result: a demo org with dozens of leads, genuine booking patterns, authentic conversation depth, and a calendar that reflects the bot's real performance — not a pre-scripted allocation

## User stories for the Analize tab

What the manager asks and sees:

1. **Funnel drop-off**: "Show me where people leave. How many said hi vs. asked about services vs. booked?" → A funnel visualization: 50 greeted → 30 asked about services → 12 checked availability → 6 booked.

2. **Lead segmentation**: "Group my leads into types." → Avatars: 15 window shoppers, 8 ready-to-buy, 4 staff-demanders, 3 price-checkers, etc.

3. **Calendar utilization**: "How full is my calendar this week? Which slots are empty?" → 65% utilized. Empty slots: Mon 14-17, Wed 11-13. Busiest: Tue/Thu mornings.

4. **Revenue projection**: "How much will I make this week from bookings?" → Confirmed: 420€. Projected (including in-progress): 580€. Last week: 350€.

5. **Conversion insight**: "Which service converts best? What time of day?" → Čiščenje obraza: 40% inquiry-to-book. Nega obraza: 25%. Best booking window: 10:00-12:00.

6. **Actionable recommendation**: "What should I change?" → "Your 14:00-16:00 slots are always empty. Consider a popoldanski popust. Also, 3 customers asked about add-ons but none bought — the AI should mention them sooner in the conversation."

## Phase 1 - Implementation

I believe this should work as a launchable script, a cheap, quick, and high-quality DeepSeek model generates the data.

Possible Step 0 things first:

1) Currently payment/Stripe, not even as a demo implementation works, we need to make this a natural and great part of the flow. AI should be able to send a proper invoice for deposits too.

2) The model used by the demo itself should properly be DeepSeek too.

3) Both infrastructures must be designed and implemented to properly handle all these 3: Correctness/quality (LLM does its job properly), Speed, very cheap. By both infrastructures I mean both the testing/script we are discussing, AND the ACE system itself. Concurrency, proper step-by-step, token usage, all must be expertly designed and implemented (LangGraph/LangChain, context saving and adding, proper model choice, fast, modular, and great code)

## Step 0

1) Remove rezerviraj buttons from the cards in the site-visitor page ✅
2) Hovering over the card, it shows possible additions ✅
3) Empower Booking through LLM/etc., so additions can be added to the booking, the LLM SOFTLY nudges upsells, when deemed appropriate.

## Simulation script

### Architecture — Three agents, one orchestrator

```
┌──────────────┐     POST /chat       ┌──────────────────┐
│  Customer    │ ──────────────────> │  ACE Receptionist │
│  Simulator   │ <────────────────── │  (the real system) │
│  (DeepSeek)  │    JSON reply       │                   │
└──────────────┘                     └──────────────────┘
       │                                      │
       │                              ┌───────┴──────────┐
       │                              │  Staff Simulator  │
       │                              │  (DeepSeek)       │
       │                              │  only for takeover│
       │                              │  scenarios        │
       │                              └──────────────────┘
       │                                      │
       └──────────┬───────────────────────────┘
                  │
          ┌───────┴──────────┐
          │   Orchestrator   │
          │   (Python script) │
          │   scripts/        │
          │   simulate_       │
          │   conversations.  │
          │   py              │
          └──────────────────┘
```

**Agent 1 — ACE Receptionist (unchanged):** The real system. Receives POST /chat, runs the full LangGraph pipeline, returns replies. Streaming preferred. This is exactly what's running on port 8000.

**Agent 2 — Customer Simulator:** A separate DeepSeek instance. It is given a demographics card (age, channel, budget, disposition, quirks) and the conversation history so far. Its job: play the role of a real salon visitor — casual, realistic Slovenian, sometimes messy, sometimes pushy, sometimes confused. It does NOT know about the salon's internal state. It only sees what the receptionist tells it.

**Agent 3 — Staff Simulator:** A separate DeepSeek instance. Only activated when the conversation reaches a takeover scenario (customer clicks "Zahtevaj osebje", or the script triggers one). It plays the role of Maja the cosmetician — warm, professional, knowledgeable about services.

**Orchestrator:** `scripts/simulate_conversations.py`. Thin — just a loop. The real work already happens inside the ACE system. The orchestrator's only job is distribution tracking + running conversations:

```python
state = load_state() or {"completed": 0, "counts": {...}, "results": []}

for i in range(state["completed"], 100):
    demo = sampler.next(state["counts"])          # weighted random, targets underfilled buckets
    sid = f"sim-{i:03d}"
    result = run_conversation(sid, demo)           # same send_chat we already tested
    state["results"].append(result)
    state["counts"] = sampler.update_counts(state["counts"], demo, result)
    state["completed"] = i + 1
    save_state(state)
```

Key properties:
- Runs conversations sequentially — no parallelism, no rate limit issues, no slot conflicts
- Each conversation gets a **fresh customer**: clean SID, clean conversation history, no context leaking from previous runs
- The Customer Simulator has no memory of previous conversations — it's a new DeepSeek call with only the current demographics prompt + this conversation's history

**Sampler:** `scripts/demographics.py`. The interesting part. Not just `random.choice()` — it tracks cumulative counts and weights draws toward underrepresented buckets so the final distribution matches the targets:

| Dimension | Mechanism |
|-----------|-----------|
| Age, Gender, Channel, Service interest, Budget | Weighted random draw — each pick reduces the weight for that bucket next time |
| Booking disposition | Same weighted draw across 3 levels |
| Behavior quirks | Sampled independently (cross-mixed with everything above) |
| Name, phone, email | Pulled from a pool of realistic Slovenian names/numbers |

All dimensions are **independent draws**. A 55-year-old VIP can be "just browsing." A 22-year-old with payment anxiety can be "eager to book." The sampler output is a plain JSON demographics card — the same format we tested in `test_single_conversation.py`.

### Conversation flow per turn

```
1. Orchestrator calls Customer Simulator (DeepSeek):
   System prompt: natural-language instructions built from sampled demographics card
   User prompt: conversation history so far + "Kaj rečeš naslednje? Odgovori SAMO z sporočilom."
   → Customer message generated

2. Orchestrator POSTs to /chat with {"message": ..., "sid": sid, "tenant_slug": "demo"}
   → ACE Receptionist processes (LLM + tools), returns JSON with "reply"

3. Orchestrator reads the reply, appends to history

4. Side effects detected from reply text or DB queries after the turn:
   - Payment URL found → follow it via POST /pay/{token}/complete
   - Staff takeover triggered → switch to Staff Simulator for remaining turns

5. Conversation ends when:
   - Customer says goodbye (detected via keyword match: "adijo", "nasvidenje", "hvala lepa")
   - Booking + payment completed
   - Max turns reached (10)

6. Next conversation: fresh SID, fresh demographics sample, no context carried over
```

### Customer demographics system

Each conversation starts with a demographics card sampled from the distributions above. The Customer Simulator sees this at the start of every turn:

```json
{
  "ime": "Mojca",
  "starost": 31,
  "spol": "ženska",
  "kanal": "Instagram",
  "nov_ali_vracajoc": "nova stranka",
  "zanima_jo": "nega obraza",
  "obcutljivost_na_ceno": "srednja",
  "dispozicija": "samo brskam, nisem prepricana ce bom kaj rezervirala",
  "posebnosti": "nobena"
}
```

> The dispozicija sets the initial tone but does NOT lock the outcome. The LLM customer decides whether to book based on how the conversation goes. A curious browser can convert; an eager buyer can bail.

### Conversation run (100 total)

100 conversations are generated. There are no fixed categories with predetermined outcomes. Demographics and dispositions are sampled from the distributions, and the results are what they are — a genuine stress test.

| Disposition | Distribution | Can end up... |
|-------------|-------------|----------------|
| Just browsing / curious | ~40 conversations | Booking if the bot impresses, leaving if not |
| Researching / planning | ~35 conversations | Booking once questions are answered, or postponing |
| Eager to book | ~25 conversations | Booking quickly, or bailing if the bot fumbles badly |

| Behavior quirk | Distribution | What it means |
|----------------|-------------|---------------|
| None | ~70% | Normal customer behavior |
| Might request staff | ~10% | Can escalate to human at any point if the bot seems unhelpful |
| Payment anxiety | ~10% | Nervous about paying online, may need reassurance |
| VIP / demanding | ~5% | Wants premium treatment, specific requests, might be picky |
| Flaky / no-show tendency | ~5% | Might book but try to reschedule or express doubt |

> Quirks are sampled independently from demographics and disposition. A VIP can be "just browsing." A payment-anxious customer can be eager to book. Everything mixes naturally.

### Technical details

**Customer Simulator prompt design:**
- System prompt: demographics card + natural-language behavioral instruction built from the sampled dimensions:
  *"Si [ime], [starost]-letna stranka kozmetičnega salona. Našel/našla si nas preko [kanal]. [nov_ali_vracajoc]. Zanima te [zanima_jo]. Glede cen si [obcutljivost_na_ceno]. Trenutno si razpoložena: [dispozicija]. [posebnosti v navodilih ce obstajajo]. Govoriš naravno slovenščino. Odgovarjaš na vprašanja receptorja. Ne veš ničesar o salonu razen tega kar ti receptor pove. Odlocitev o rezervaciji sprejmes glede na potek pogovora — nisi programiran/a da rezerviras ali da ne rezerviras."*
- Each turn: full conversation history + "Kaj rečeš naslednje? Odgovori SAMO z sporočilom, nič drugega."
- Model: deepseek-chat, temperature 0.9 (higher for genuine variability)

**Staff Simulator prompt:**
- System prompt: "Ti si Maja, kozmetičarka v salonu Lepota & Sprostitev. Si topla, profesionalna, poznaš vse storitve in cene. Govoriš sproščeno slovenščino."
- Activated via POST /chat/staff with JWT auth
- Each turn: conversation history + staff-side context

**Timing & slots:**
- Bookings spread across 5 working days (Mon-Fri)
- No pre-generated slot allocation. The Customer Simulator asks "kaj imate prosto v [dan/teden]" like a real person would, and the booking lands in whatever slot the receptionist offers and the customer accepts.
- Calendar fills naturally — mornings tend to get busier because more simulated customers prefer morning slots (sampled distribution: morning 45%, midday 20%, afternoon 35%).

**Resume support:**
- Script saves progress after each conversation to a JSON state file
- If interrupted, resumes from the last completed conversation
- Conversation IDs are deterministic (based on scenario index) to avoid duplicates

**Output:**
- All data lives in PostgreSQL (leads, messages, bookings, events) — the same tables the org dashboard queries. Open the dashboard after a run and every simulated lead looks indistinguishable from a real customer.
- A summary JSON generated at the end: {total, booked, dropped, payment_issues, staff_takeovers, add_ons_sold, etc.}
- When the Analize tab's AI queries this data, it finds real funnel leaks and real upsell gaps — because the data passed through the real system, not a mock.

### Implementation plan

Already tested and working (`test_single_conversation.py` proves the full pipeline):

1. ✅ `POST /chat` — booking, payment, messages, leads all persist in PostgreSQL
2. ✅ DeepSeek Customer Simulator — generates natural Slovenian replies from demographics prompt
3. ✅ Payment completion — `POST /pay/{token}/complete` marks payment as `paid`
4. ✅ Dashboard visibility — leads appear at `http://localhost:8000/demo/dashboard`

What remains to build:

1. `scripts/demographics.py` — Sampler class with weighted distributions, cumulative tracking, independent cross-mixing
2. `scripts/simulate_conversations.py` — Orchestrator: thin loop calling sampler + `run_conversation()` + state save
3. `scripts/person_pool.json` — ~100 realistic Slovenian names, phone numbers, email addresses (pulled by sampler)
4. Staff Simulator — reuse same DeepSeek pattern as Customer Simulator, just different system prompt. Activated when the conversation triggers a takeover (customer says "želim osebje" or clicks staff button). Sends messages via `POST /chat/staff`.
5. Resume support — trivial JSON state file, deterministic SIDs (`sim-000` through `sim-099`)
6. Summary generation — after all 100 complete, query PostgreSQL for `{total, booked, dropped, payment_issues, staff_takeovers, add_ons_sold, avg_turns, etc.}`

> The heavy lift is already done. The orchestrator is ~50 lines of Python. The sampler is the only piece with real logic.
