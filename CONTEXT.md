# ACE — Complete Project Context

## What This Is

ACE is an **AI SDR (Sales Development Rep) for B2B companies**. It's an AI chat widget that qualifies website visitors in real-time, extracts their business profile, and pushes them into an instant meeting with the sales team — or schedules a discovery call for later.

The product: a B2B company embeds ACE on their site. Visitors get greeted by an AI that asks what they need, qualifies them (budget, problem, company, timeline), and within 2-3 turns offers a live handoff to the sales team. If the team is offline, ACE books a discovery call for the next working day.

**The beauty salon vertical was a demo/testing surface.** The real product is B2B lead qualification + instant meeting booking.

## Architecture (Single Python Service)

```
Visitor Browser
    │
    ▼
┌─────────────────────────────────┐
│  Python FastAPI backend/        │  ← ONE process. ~700 lines.
│  Port 8000                      │
│                                 │
│  Serves Angular SPA (static)    │
│  REST + WebSocket API           │
│  Auth (JWT)                     │
│  Chat → calls LangGraph directly│
│  Video takeover (LiveKit)       │
│  Lead/org/user management       │
└──────┬──────────────┬───────────┘
       │              │
       ▼              ▼
  PostgreSQL      LiveKit
  (port 5433)     (port 7880)
```

**There is no Java.** The old Java Spring Boot backend was deleted and replaced with Python FastAPI. The `app/` directory is an AI library imported directly by `backend/`.

## Directory Map

```
ACE/
├── backend/                  ★ THE SERVER — read this first
│   ├── main.py               FastAPI app, lifespan seeds demo data, SPA fallback
│   ├── routes_chat.py        /chat, /chat/stream, /chat/staff, events, leads, bookings
│   ├── routes_admin.py       /api/admin/organizations, /api/admin/users
│   ├── models.py             SQLAlchemy models (Organization, User, Lead, etc.)
│   ├── auth.py               JWT auth, password hashing (bcrypt)
│   ├── events.py             Event pub/sub with WebSocket fanout
│   ├── database.py           Async SQLAlchemy engine + session
│   ├── livekit_token.py      LiveKit JWT token generation (manager + visitor)
│   └── static/               Built Angular SPA served by main.py
│
├── app/                      ★ AI LIBRARY — imported by backend/
│   ├── qualification/
│   │   ├── graph.py          LangGraph: builds system prompt, runs tools, generates reply
│   │   ├── state.py          TypedDict + dataclass types for graph state
│   │   ├── tools.py          B2B tools (context, contact, schedule_call, request_team, update_profile)
│   │   └── runtime_context.py  Builds runtime context from qualifier config
│   └── services/
│       └── llm_service.py    OpenAI client wrapper (JSON, text, stream, tool calls)
│
├── angular-visitor/           ★ FRONTEND — Angular 19 SPA
│   ├── src/app/
│   │   ├── receptionist-chat/   Main chat widget
│   │   ├── staff-video/         LiveKit video overlay
│   │   ├── service-cards/       Service browsing cards
│   │   ├── calendar-picker/     Appointment date/time picker
│   │   ├── header/              Status bar (open/closed)
│   │   ├── admin/               Admin panel (orgs, users)
│   │   ├── org-dashboard/       Per-org dashboard (3 tabs: KONVERZACIJE, AI RECEPTOR, REZERVACIJE)
│   │   ├── login/               Login page
│   │   └── services/
│   │       ├── salon.service.ts       Core state: messages, staffState, send, poll
│   │       ├── chat-api.service.ts    HTTP layer: /chat, /chat-events/poll
│   │       ├── org-dashboard.service.ts  Staff API: leads, takeover, goLive/endLive
│   │       └── admin.service.ts       Admin API: orgs, users
│   └── proxy.conf.json         Dev proxy → port 8000
│
├── docker-compose-simple.yml   PostgreSQL + LiveKit + Backend
├── docker/livekit.yaml         LiveKit server config (devkey/devsecret)
├── .env                        Credentials (OpenAI key, DB URL, LiveKit keys)
├── scripts/
│   ├── simulate_b2b.py          B2B conversation simulator
│   ├── sim_b2b_state.json       Simulator state for resume support
│   └── ensure_demo_data.py      Demo data seeding
└── docs/                        Additional specs
```

## How It Runs

### Start Infrastructure
```bash
docker compose -f docker-compose-simple.yml up -d
# Starts: PostgreSQL (5433), LiveKit (7880), Backend (8000)
```

### Start Backend (local dev)
```bash
cd backend
source ../venv/bin/activate
uvicorn main:app --port 8000 --reload
```

### Angular Dev Server
```bash
cd angular-visitor
npm start   # port 4200, proxies API to 8000
```

### Production
```bash
cd angular-visitor && npm run build
cp -r dist/angular-visitor/browser/* ../backend/static/
# Backend at port 8000 serves everything
```

On first startup, `backend/main.py` lifespan auto-seeds:
- Demo organization (`slug: demo`, `name: ACE`)
- Admin user (`admin` / `test123`, role `PLATFORM_ADMIN`)
- Default qualifier: "AI Svetovalec" — Slovenian B2B sales qualification prompt

## Data Model (PostgreSQL)

All models in `backend/models.py`, using async SQLAlchemy:

| Table | Key Columns | Purpose |
|---|---|---|
| `organizations` | id, name, slug, active | Tenant/B2B company |
| `users` | id, username, password_hash, role, organization_id | Auth (PLATFORM_ADMIN, ORG_ADMIN, ORG_USER) |
| `leads` | id, organization_id, sid, status, takeover_active, qualifier_profile | Visitor conversation session |
| `conversation_messages` | id, lead_id, role (user/assistant/staff), text | Chat history |
| `lead_events` | id, organization_id, sid, event_type, payload_json | Event log for polling |
| `qualifiers` | id, organization_id, name, system_prompt, status | AI behavior config per org |
| `bookings` | id, organization_id, lead_id, service_name, booking_date, booking_time | Scheduled discovery calls |

**SID**: Unique session ID per visitor conversation (`sid_` + 12 hex chars).

**LeadStatus enum**: `OPEN_CHAT`, `HUMAN_TAKEOVER`, `CLOSED`

**Qualifier status**: `draft`, `live`, `archived`. One live qualifier per org.

## API Surface

### Public (no auth)
| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Visitor sends message, gets AI reply |
| POST | `/chat/stream` | Streaming version (SSE tokens) |
| GET | `/chat-events/poll` | Poll for real-time events |
| GET | `/api/public/organizations/{slug}/live-session?sid=` | Check if video is live |
| GET | `/api/public/organizations/{slug}/leads/{sid}/messages` | Get chat history |
| POST | `/api/public/organizations/{slug}/leads/{sid}/request-staff` | Request human |
| POST | `/login` | Form login → JWT |

### Authenticated (JWT Bearer)
| Method | Path | Purpose |
|---|---|---|
| POST | `/chat/staff` | Staff takeover message |
| GET | `/api/organizations/{org_id}/leads` | List leads with profiles, scores, bookings |
| GET | `/api/organizations/{org_id}/leads/{sid}/messages` | Lead messages |
| POST | `/api/organizations/{org_id}/leads/{sid}/takeover/end` | End takeover |
| DELETE | `/api/organizations/{org_id}/leads/{sid}` | Delete lead |
| POST | `/api/organizations/{org_id}/live-sessions/go-live` | Start video session |
| POST | `/api/organizations/{org_id}/live-sessions/end` | End video session |
| GET | `/api/organizations/{org_id}/bookings` | List bookings |
| POST | `/api/organizations/{org_id}/bookings` | Create booking |
| DELETE | `/api/organizations/{org_id}/bookings/{id}` | Cancel booking |

### Admin (PLATFORM_ADMIN only)
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/admin/organizations` | List/create orgs |
| GET/POST | `/api/admin/users` | List/create users |

### Chat request/response
```json
// Request
{"message": "Zdravo, rabimo AI za avtomatizacijo prodaje", "sid": "sid_abc123", "tenant_slug": "demo"}
// Response
{"sid": "sid_abc123", "reply": "Živjo! ... Bi želeli da se naša ekipa takoj vključi?", "chatMode": "open", ...}
```

## AI Flow (how chat works)

```
Visitor sends message
  │
  ▼
backend/routes_chat.py: POST /chat
  │
  ├─ takeover_active? → AI stays silent (staff handles it)
  │
  ├─ Extract phone/email from message text via regex
  │
  ├─ Save user message to conversation_messages
  │
  ├─ Load qualifier from DB (find by org_id + status='live')
  │
  ├─ Set DB context for tools (org_id, sid, phone, email)
  │
  ├─ Load recent messages (last 20)
  │
  └─ Call app.qualification.graph.run_qualification_graph()
       │
       ├─ 1. Build system prompt (_build_agent_prompt)
       │     Turn-based instruction: greet → qualify → offer team takeover → schedule call
       │
       ├─ 2. Run tools phase (_run_tools_phase)
       │     LLM calls: ace_get_context, ace_check_contact, ace_update_profile,
       │     ace_schedule_call, ace_request_team
       │     Deterministic tool execution via execute_tool()
       │     If contact exists and message mentions date/time but LLM didn't call
       │     ace_schedule_call, force a second tool-call pass
       │
       └─ 3. Generate final Slovenian reply
            If tools were called → llm.call_json_response()
            If no tools → llm.stream_reply() for streaming
```

### B2B Tools (deterministic, no LLM)

In `app/qualification/tools.py`:

- **ace_get_context** — Open/closed status, working hours (Mon-Fri 9-17), next working day
- **ace_check_contact** — Do we already have visitor's phone or email?
- **ace_schedule_call** — Book a 30-min discovery call (persists to bookings table, publishes event)
- **ace_request_team** — Request live team takeover (only during working hours)
- **ace_update_profile** — Record business profile fields: use_case, company_type, scale, current_system, timeline, business_name, budget, problem

### Turn-Based Instruction (from graph.py)

| Turn | Instruction |
|---|---|
| **0 (first contact)** | Greet, explain what ACE does (1 sentence), ask what brought them. If they mention budget or problem → immediately call ace_update_profile. |
| **1 (second exchange)** | Answer, be helpful. If lead is serious (has budget, knows what they want) → IMMEDIATELY offer live team takeover NOW via ace_request_team. "Bi želeli da se naša ekipa takoj vključi v pogovor?" Do NOT ask for email if you can offer live staff. |
| **2 (third exchange)** | Lead is already engaged. If they haven't accepted instant takeover → offer ace_schedule_call for a later term. |
| **3+ (close)** | If lead hasn't booked → ask for email/phone OR offer ace_schedule_call. Don't repeat yourself. Be brief. |

**Non-working hours (closed):**
- Turn 0: Greet, mention we're closed (9-17), ask what brought them
- Turn 1: CALL ace_schedule_call NOW. Don't ask for anything — just book. Default: tomorrow at 10:00
- Turn 2+: If you haven't called ace_schedule_call — DO IT NOW. If done, say it's booked and goodbye.

### Lead Profile Extraction

After the AI generates a reply, `routes_chat.py` extracts business profile fields using:
1. **Tool results** — If ace_update_profile was called, capture the fields from tool output
2. **Regex extraction** — Extract business_name, budget, problem from conversation text
3. **LLM extraction fallback** — If regex missed fields, call LLM for structured extraction

Extracted fields: `business_name`, `budget`, `problem`, `company_type`, `scale`, `current_system`, `timeline`, `use_case`

All saved to `lead.qualifier_profile` (JSONB in PostgreSQL).

## Video Takeover Flow

```
1. Staff calls POST /api/organizations/{id}/live-sessions/go-live {"sid":"..."}
   → backend creates LiveKit manager token
   → publishes live_session.started event
   → returns {roomName, token, wsUrl}

2. Visitor's StaffVideoComponent polls live-session endpoint every 3s
   → When status='live': connects to LiveKit room as visitor (subscribe-only)
   → Renders remote video with "● V ŽIVO" badge overlay

3. Staff calls POST .../live-sessions/end {"sid":"..."}
   → publishes live_session.ended event
   → Visitor component disconnects, hides video
```

### LiveKit tokens (`backend/livekit_token.py`)
- Room name format: `ace-{orgSlug}-{sid}`
- Manager token: can publish + subscribe
- Visitor token: subscribe-only
- Credentials from .env: `ACE_LIVEKIT_API_KEY`, `ACE_LIVEKIT_API_SECRET`

## Event System

`backend/events.py` — in-process pub/sub with WebSocket fanout.

Events are saved to `lead_events` table and pushed to connected WebSocket clients.

Poll endpoint: `GET /chat-events/poll?sid=...&since={seq}`

Key events:
- `message.created` — New chat message (user/assistant/staff)
- `lead.takeover.started` / `lead.takeover.ended` — Staff takeover state
- `live_session.started` / `live_session.ended` — Video session state
- `lead.staff-requested` — Visitor requested human
- `lead.touched` — Generic lead update
- `booking.created` / `booking.cancelled` — Booking events

## Qualifier System

Each B2B company gets a **Qualifier** that defines how the AI behaves:
- `system_prompt` — core instructions for the LLM
- `assistant_style` — tone (e.g., "prijazen, direkten, posloven")
- `goal_definition` — what the AI should achieve
- `field_schema` — fields to extract from conversation
- `required_fields` — fields that matter most
- `scoring_rules`, `band_thresholds` — lead scoring
- `takeover_rules`, `video_offer_rules` — when to offer human/video
- `contact_capture_policy` — when to ask for contact info

Default qualifier (auto-seeded):
```
name: "AI Svetovalec"
slug: "ai-receptor"
system_prompt: "Ti si AI Svetovalec za ACE — podjetje, ki razvija AI recepcijske
  rešitve za avtomatizacijo sprejema strank. Toplo pozdravi obiskovalce, vprašaj
  jih po njihovih poslovnih potrebah (količina strank, obstoječi sistemi, urnik,
  proračun), kvalificiraj lead in, če je primeren, ponudi klic z ekipo."
assistant_style: "prijazen, direkten, posloven"
status: "live"
```

## Angular Frontend Architecture

### Routes
| Path | Component | Purpose |
|---|---|---|
| `/` | ReceptionistChatComponent | Visitor chat (defaults to demo org) |
| `/:slug` | ReceptionistChatComponent | Visitor chat for specific org |
| `/:slug/dashboard` | OrgDashboardComponent | Staff dashboard |
| `/login` | LoginComponent | Login page |
| `/admin` | AdminComponent | Platform admin panel |

### OrgDashboardComponent (3 tabs)
- **KONVERZACIJE** — Lead list with filters, thread view, staff takeover (text + video)
- **AI RECEPTOR** — Qualifier configuration editor
- **REZERVACIJE** — Booking timeline (day/week view), booking cards, stats

## Environment Variables (.env)

```
# AI
OPENAI_API_KEY=sk-...
ACE_LLM_PROVIDER=openai
ACE_LLM_MODEL=gpt-4.1-mini
ACE_SECRET=...                    # JWT signing secret

# Database
DATABASE_URL=postgresql://ace_user:test_password_123@localhost:5433/ace_platform

# LiveKit
ACE_LIVEKIT_WS_URL=ws://localhost:7880
ACE_LIVEKIT_API_KEY=devkey
ACE_LIVEKIT_API_SECRET=devsecretkey_for_local_livekit_32chars
```

## Key Design Decisions

1. **Single Python process** — No microservices. `backend/` is the entire server. `app/` is a library imported directly.
2. **Direct import, no HTTP between services** — `backend/routes_chat.py` does `from app.qualification.graph import run_qualification_graph`.
3. **Turn-based AI behavior** — The system prompt changes per turn count. Aggressive push for live takeover on turn 1.
4. **Deterministic tools** — B2B tools execute real logic (DB writes, event publishing). The LLM decides which tools to call, but tool outputs are deterministic.
5. **Polling for real-time** — Frontend polls `/chat-events/poll` every 1s. WebSocket only for internal pub/sub.
6. **LiveKit for video** — One-way: staff publishes, visitor subscribes.
7. **Regex + LLM extraction** — Lead profiles extracted via regex first (fast, reliable), with LLM fallback for fields regex misses.
8. **SID-based sessions** — Visitors don't log in. Each conversation gets a unique `sid` stored in sessionStorage.
9. **Discovery calls** — Bookings are 30-min "Discovery Call" meetings (free, for sales qualification).

## Files You Can Ignore

- `ace-mobile/` — Legacy Ionic mobile app, not part of current stack
- `app/api/`, `app/portal/`, `app/auth/` — Legacy API/auth from old multi-service architecture
- `app/models/orm.py` — Legacy SQLAlchemy models with column mismatches
- `docs/archive/` — Historical docs referencing deleted Java code
- `test_*.py`, `tests/` — Test files (may be outdated)
- `data/` — Legacy conversation flow JSON files

## What Matters Right Now

The working stack:

| Layer | Files | Lines |
|---|---|---|
| Server | `backend/main.py`, `routes_chat.py`, `routes_admin.py` | ~500 |
| Models | `backend/models.py` | ~110 |
| Auth | `backend/auth.py` | ~55 |
| Events | `backend/events.py` | ~26 |
| LiveKit | `backend/livekit_token.py` | ~40 |
| AI Graph | `app/qualification/graph.py`, `state.py`, `tools.py`, `runtime_context.py` | ~550 |
| LLM Client | `app/services/llm_service.py` | ~130 |
| Frontend | `angular-visitor/src/app/` | ~1,200 |

**Total: ~2,600 lines of meaningful code.**
