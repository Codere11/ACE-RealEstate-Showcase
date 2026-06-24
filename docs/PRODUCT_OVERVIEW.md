# ACE — Product Vision

## North Star

Make ACE a **no-brainer** for B2B companies that have at least one salesperson and want to capture more leads from their website.

## What ACE Replaces

The "Contact Us" form. The dead email inbox. The visitors who land on your site, browse, and leave without ever talking to a human.

ACE puts an AI SDR on your site that qualifies visitors and books them into live meetings with your sales team — instantly.

## How It Works

1. Visitor lands on your B2B website
2. ACE greets them in chat, asks what they need
3. Qualifies in 2-3 turns: budget? problem? timeline? company?
4. If qualified: **"Bi želeli da se naša ekipa takoj vključi v pogovor?"**
5. Sales guy joins live — text or video
6. If team is offline: ACE books a discovery call for tomorrow

## The Feel

Like having your best salesperson sitting on your website 24/7. Visitors don't fill forms — they talk. The AI qualifies. The human closes.

## Core Product Layers

### 1. AI Qualifier (Visitor Side — Angular SPA)
- Greets visitors naturally
- Qualifies: extracts business name, budget, problem, timeline
- Pushes for instant sales team takeover on turn 1
- Falls back to scheduling a discovery call
- Shows open/closed hours with live status
- Hands off to human staff with premium fade-in

### 2. Live Staff Handoff
- **Instant takeover** — AI offers live team join within 2 turns
- **Video (LiveKit)** — One-way: sales publishes camera, visitor watches
- **Discovery call scheduling** — When team is offline, book for next working day

### 3. Staff Dashboard
- Lead list with qualification scores and extracted profiles
- Conversation thread view with takeover controls
- Live video handoff initiation
- Booking timeline (day/week view)
- Qualifier configuration editor per org
- Open/closed status control

### 4. AI Brain (Python + LangGraph)
- Turn-based conversation flow: greet → qualify → offer takeover → schedule
- B2B tools: context, contact check, call scheduling, team request, profile update
- Lead profile extraction: regex + LLM fallback
- Working hours awareness — different behavior when team is offline

## Implementation Shape
- **Angular 19** — visitor-side SPA + staff dashboard
- **Python FastAPI** — single backend (API + AI + static serving)
- **LangGraph + OpenAI** — AI qualification runtime
- **PostgreSQL** — persistence
- **LiveKit** — live video handoff

## Where to read next
- `CONTEXT.md` — complete project overview
- `ARCHITECTURE.md` — high-level design
- `Startup.txt` — runbook
- `docs/AI_QUALIFIER_SPEC.md` — qualifier system
- `docs/VIDEO_TAKEOVER_SPEC.md` — video takeover
