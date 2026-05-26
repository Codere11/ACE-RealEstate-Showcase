# ACE Reception Services — Complete Project Context

## What This Is

ACE Reception Services is an **AI receptionist platform for Slovenian beauty salons (kozmeticni saloni)**. It's a digital front desk: greet visitors, answer questions about services, book appointments, and hand off to human staff via live video — all through a chat interface.

The feel: walking into a real store with a real receptionist. Just digital.

## Architecture (Single Python Service)

```
Visitor Browser
    │
    ▼
┌─────────────────────────────────┐
│  Python FastAPI backend/        │  ← ONE process. 662 lines total.
│  Port 8000                      │
│                                 │
│  Serves Angular SPA (static)    │
│  REST + WebSocket API           │
│  Auth (JWT)                     │
│  Chat → calls LangGraph directly│
│  Camera takeover (LiveKit)      │
│  Lead/org/user management       │
└──────┬──────────────┬───────────┘
       │              │
       ▼              ▼
  PostgreSQL      LiveKit
  (port 5433)     (port 7880)
```

**There is no Java.** It was deleted. The old `app/` directory is now just an AI library imported by `backend/`.

## Directory Map

```
ACE-RealEstate/
├── backend/                  ★ THE SERVER — read this first
│   ├── main.py               FastAPI app, lifespan (seeds demo data), SPA fallback
│   ├── routes_chat.py        /chat, /chat/staff, poll events, leads, live sessions
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
│   │   ├── graph.py          LangGraph: classify intent → route to stage node → reply
│   │   ├── state.py          TypedDict + dataclass types for graph state
│   │   ├── prompts.py        Slovenian system prompts per conversation stage
│   │   ├── tools.py          Salon tools (services, availability, booking, staff request)
│   │   └── runtime_context.py  Builds runtime context from qualifier config
│   └── services/
│       └── llm_service.py    OpenAI client wrapper (JSON, text, stream, tool calls)
│
├── angular-visitor/           ★ FRONTEND — Angular 19 SPA
│   ├── src/app/
│   │   ├── receptionist-chat/   Main chat widget (header, messages, input, actions)
│   │   ├── staff-video/         LiveKit video overlay (16:9, 2.4s fade-in, retry/reconnect)
│   │   ├── service-cards/       Service browsing cards
│   │   ├── calendar-picker/     Appointment date/time picker
│   │   ├── header/              Status bar (open/closed, salon name)
│   │   ├── admin/               Admin panel (orgs, users)
│   │   ├── org-dashboard/       Per-org dashboard (3 tabs: KONVERZACIJE, AI RECEPTOR, REZERVACIJE)
│   │   ├── login/               Login page
│   │   └── services/
│   │       ├── salon.service.ts       Core state: messages, staffState, send, poll, live events
│   │       ├── chat-api.service.ts    HTTP layer: /chat, /chat-events/poll, /leads/.../messages
│   │       ├── org-dashboard.service.ts  Staff API: leads, messages, takeover, goLive/endLive
│   │       └── admin.service.ts       Admin API: orgs, users
│   └── proxy.conf.json         Dev proxy → port 8000 (backend)
│
├── docker-compose-simple.yml   PostgreSQL + LiveKit
├── docker/livekit.yaml         LiveKit server config (devkey/devsecret)
├── .env                        Credentials (OpenAI key, DB URL, LiveKit keys)
└── docs/                       Additional specs (see below)
```

## How It Runs

### Start Infrastructure
```bash
docker compose -f docker-compose-simple.yml up -d
# Starts: PostgreSQL (5433), LiveKit (7880)
```

### Start Backend
```bash
cd backend
source ../venv/bin/activate
uvicorn main:app --port 8000 --reload
```

### Angular Dev Server (optional — for frontend development)
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
- Demo organization (`slug: demo`, `name: Demo Agency`)
- Admin user (`admin` / `test123`, role `PLATFORM_ADMIN`)
- AI Receptor qualifier (Slovenian beauty salon system prompt)

## Data Model (PostgreSQL)

All models in `backend/models.py`, using async SQLAlchemy with explicit Column definitions (no ORM mismatch):

| Table | Key Columns | Purpose |
|---|---|---|
| `organizations` | id, name, slug, active | Tenant/salon |
| `users` | id, username, password_hash, role, organization_id | Auth (PLATFORM_ADMIN, ORG_ADMIN, ORG_USER) |
| `leads` | id, organization_id, sid, status, takeover_active, qualifier_profile | Visitor conversation session |
| `conversation_messages` | id, lead_id, role (user/assistant/staff), text | Chat history |
| `lead_events` | id, organization_id, sid, event_type, payload_json | Event log for polling |
| `qualifiers` | id, organization_id, name, system_prompt, status | AI behavior config per org |

**SID**: Unique session ID per visitor conversation (`sid_` + 12 hex chars).

**LeadStatus enum**: `SURVEY`, `OPEN_CHAT`, `HUMAN_TAKEOVER`, `CLOSED`

**Qualifier status**: `draft`, `live`, `archived`. One live qualifier per org.

## API Surface (all in `backend/routes_chat.py` + `backend/routes_admin.py`)

### Public (no auth)
| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Visitor sends message, gets AI reply |
| GET | `/chat-events/poll` | Poll for real-time events (takeover, messages) |
| GET | `/api/public/organizations/{slug}/live-session?sid=` | Check if camera is live |
| GET | `/api/public/organizations/{slug}/leads/{sid}/messages` | Get chat history |
| POST | `/api/public/organizations/{slug}/leads/{sid}/request-staff` | Request human |

### Authenticated (JWT Bearer)
| Method | Path | Purpose |
|---|---|---|
| POST | `/login` | Form login (username, password) → JWT |
| POST | `/chat/staff` | Staff takeover message (starts takeover) |
| GET | `/api/organizations/{org_id}/leads` | List leads |
| GET | `/api/organizations/{org_id}/leads/{sid}/messages` | Lead messages |
| POST | `/api/organizations/{org_id}/leads/{sid}/takeover/end` | End takeover |
| POST | `/api/organizations/{org_id}/live-sessions/go-live` | Start camera session |
| POST | `/api/organizations/{org_id}/live-sessions/end` | End camera session |

### Admin (PLATFORM_ADMIN only)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/admin/organizations` | List all orgs |
| POST | `/api/admin/organizations` | Create org (auto-seeds qualifier) |
| GET | `/api/admin/users` | List all users |
| POST | `/api/admin/users` | Create user |

### Chat request/response format
```json
// Request
{"message": "Hello", "sid": "sid_abc123", "tenant_slug": "demo"}
// Response
{"sid": "sid_abc123", "reply": "Dober dan! ...", "chatMode": "open", ...}
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
  ├─ Save user message to conversation_messages
  │
  ├─ Load qualifier from DB (find by org_id + status='live')
  │
  ├─ Load recent messages (last 8)
  │
  └─ Call app.qualification.graph.run_qualification_graph()
       │
       ├─ 1. classify_intent (greeting|discovery|availability|booking|handoff|idle)
       │     Uses LLMService.call_json() with classify prompt
       │
       ├─ 2. Route to stage-specific node
       │
       └─ 3. _reply_for_stage(stage)
            Uses LLMService.call_with_tools() → salon tools (get_context, get_services,
            check_availability, book_appointment, request_staff)
            → LLM generates final Slovenian reply
```

### Conversation Stages
- **greeting** — First contact. Mentions hours, briefly lists services, asks how to help.
- **discovery** — Visitor asking about services. Answers directly.
- **availability** — Visitor wants to book. Shows free slots.
- **booking** — Visitor selected slot. Confirms reservation.
- **handoff** — Visitor wants human. Connects or offers booking if closed.
- **idle** — Just chatting. Brief, warm response.

### Salon Tools (deterministic, no LLM)
In `app/qualification/tools.py`:
- `salon_get_context` — Open/closed status, today's free slots, next working day
- `salon_get_services` — 3 services: Nega obraza (45min/35€), Maska obraza (30min/25€), Čiščenje obraza (60min/50€)
- `salon_check_availability` — Free slots for a date, per duration
- `salon_book_appointment` — Books a slot (in-memory for now)
- `salon_request_staff` — Staff request (open: connects, closed: offers next working day)

Hours: Mon-Fri 9:00–18:00. Appointment slots every 45/30/60 min, lunch break 12:00–12:45 excluded.

## Camera Takeover Flow

```
1. Staff calls POST /api/organizations/{id}/live-sessions/go-live {"sid":"..."}
   → backend creates LiveKit manager token
   → publishes live_session.started event
   → returns {roomName, token, wsUrl}

2. Angular StaffVideoComponent (staff-video.component.ts)
   → Listens for staff messages (onStaffMessage callback)
   → Polls GET /api/public/organizations/{slug}/live-session?sid=... every 3s
   → When status='live' and token present:
     → Connects to LiveKit room as visitor (subscribe-only)
     → Renders remote video track in <video id="livekit-video">
     → Shows animated overlay with "● V ŽIVO" badge

3. Staff calls POST .../live-sessions/end {"sid":"..."}
   → publishes live_session.ended event
   → Visitor component disconnects, hides video
```

### LiveKit tokens (`backend/livekit_token.py`)
- Room name format: `ace-{orgSlug}-{sid}`
- Manager token: can publish + subscribe
- Visitor token: subscribe-only
- Credentials from .env: `ACE_LIVEKIT_API_KEY`, `ACE_LIVEKIT_API_SECRET`
- Local dev: key=devkey, secret=devsecretkey_for_local_livekit_32chars

## Event System

`backend/events.py` — in-process pub/sub with WebSocket fanout.

Events are:
1. Saved to `lead_events` table (for polling)
2. Pushed to connected WebSocket clients (subscribed by sid)

Poll endpoint: `GET /chat-events/poll?sid=...&since={seq}`

Key events:
- `message.created` — New chat message (user/assistant/staff)
- `lead.takeover.started` / `lead.takeover.ended` — Staff takeover state
- `live_session.started` / `live_session.ended` — Camera session state
- `lead.staff-requested` — Visitor requested human
- `lead.touched` — Generic lead update

## Angular Frontend Architecture

### Routes (`app.routes.ts`)
| Path | Component | Purpose |
|---|---|---|
| `/` | ReceptionistChatComponent | Visitor chat (defaults to demo org) |
| `/:slug` | ReceptionistChatComponent | Visitor chat for specific org |
| `/:slug/dashboard` | OrgDashboardComponent | Staff dashboard |
| `/login` | LoginComponent | Login page |
| `/admin` | AdminComponent | Platform admin panel |

### Tenant detection (`environment.ts`)
Tenant slug is resolved by:
1. `?org={slug}` query parameter
2. First path segment (`/{slug}`)
3. Default: `demo`

### Key Services
- **SalonService** (`salon.service.ts`) — Central state: messages signal, staffState signal, connectionStatus, open/closed status. Handles send, poll, event processing, staff state transitions.
- **ChatApiService** (`chat-api.service.ts`) — HTTP layer with retry logic. Calls `/chat`, `/chat-events/poll`, `/api/public/organizations/{slug}/leads/{sid}/messages`.

### OrgDashboardComponent (3 tabs)
- **KONVERZACIJE** — Lead list with filters, thread view, staff takeover (text + live camera)
- **AI RECEPTOR** — Qualifier configuration editor
- **REZERVACIJE** — Booking timeline (day/week view), booking cards with status actions, "Nova rezervacija" modal, filters, stats

### StaffVideoComponent
- Polls live-session endpoint every 3s when staff takeover is active
- Uses `livekit-client` npm package to connect to LiveKit room
- Renders remote video in `<video id="livekit-video">`
- CSS: fixed top-center, 16:9 widescreen, 2.4s fade-in with retry/reconnect
- Auto-disconnects on `live_session.ended` event

## Qualifier System

Each organization has a **Qualifier** that defines how the AI receptionist behaves:
- `system_prompt` — core instructions for the LLM
- `assistant_style` — tone (e.g., "prijazen, topel, profesionalen")
- `goal_definition` — what the AI should achieve
- `field_schema` — fields to extract from conversation
- `required_fields` — fields that matter most
- `scoring_rules`, `band_thresholds` — lead scoring
- `takeover_rules`, `video_offer_rules` — when to offer human/video
- `contact_capture_policy` — when to ask for contact info

Default qualifier (auto-seeded for every org, including new ones):
```
name: "AI Receptor"
slug: "ai-receptor"
system_prompt: "Ti si AI Receptor za kozmetični salon. Toplo pozdravi obiskovalce,
  odgovarjaj na vprašanja o storitvah (nega obraza 45min/35€, maska obraza 30min/25€,
  čiščenje obraza 60min/50€), pomagaj pri izbiri tretmajev in rezerviraj termine.
  Bodi prijazen, profesionalen in ustrežljiv. Salon je odprt od 9:00 do 18:00."
assistant_style: "prijazen, topel, profesionalen"
status: "live"
```

The qualifier is loaded from DB by `backend/routes_chat.py` and passed to `run_qualification_graph()` which uses it via `runtime_context.py` to build context snippets and prompt blocks.

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

## Database Connections

Two separate DB connections exist (connecting to the same PostgreSQL):
1. **`backend/database.py`** — async SQLAlchemy (`asyncpg` driver). Used by `backend/` routes.
2. **`app/core/db.py`** — sync SQLAlchemy (`psycopg2` driver). Used by `app/` services and scripts.

Both read `.env` for `DATABASE_URL`. The `backend/` models use explicit `Column()` definitions that match the actual DB schema exactly (no mismatch).

## Key Design Decisions

1. **Single Python process** — No microservices. `backend/` is the entire server. `app/` is a library.
2. **Direct import, no HTTP between services** — `backend/routes_chat.py` does `from app.qualification.graph import run_qualification_graph`. No REST call to a separate AI service.
3. **LangGraph for conversation flow** — The AI uses a directed graph: classify → route → reply. Not an open-ended agent loop.
4. **Deterministic tools** — Salon data (services, hours, slots) is hardcoded in `app/qualification/tools.py`. The LLM calls these tools but the tool outputs are deterministic, not LLM-generated.
5. **Polling for real-time** — No WebSocket between frontend and backend for events (the WS in `main.py` is for internal pub/sub). Frontend polls `/chat-events/poll` every 1s.
6. **LiveKit for video** — One-way video: staff publishes, visitor subscribes. Visitor camera/mic stay off.
7. **Qualifier system** — Configurable AI behavior per organization, seeded with Slovenian beauty salon defaults.
8. **SID-based sessions** — Visitors don't log in. Each conversation gets a unique `sid` stored in sessionStorage.

## Files You Can Ignore

- `ace-mobile/` — Legacy Ionic mobile app, not part of current stack
- `app/api/` (agent.py, chat.py, chats.py, funnel.py, etc.) — Legacy API routes from the old multi-service architecture, not used by `backend/`
- `app/portal/` — Legacy portal routes, not used
- `app/auth/` — Legacy auth (uses old user model), not used by `backend/`
- `app/models/orm.py` — Legacy SQLAlchemy models with column name mismatches, not used by `backend/`
- `docs/archive/` — Historical docs referencing deleted Java code
- `scripts/` — Migration and seed scripts from the old architecture
- `test_*.py`, `tests/` — Test files (may be outdated)

## What Matters Right Now

The working, production-ready stack is:

| Layer | Files | Lines |
|---|---|---|
| Server | `backend/main.py`, `routes_chat.py`, `routes_admin.py` | ~440 |
| Models | `backend/models.py` | ~110 |
| Auth | `backend/auth.py` | ~55 |
| Events | `backend/events.py` | ~26 |
| LiveKit | `backend/livekit_token.py` | ~40 |
| AI Graph | `app/qualification/graph.py`, `state.py`, `prompts.py`, `tools.py`, `runtime_context.py` | ~550 |
| LLM Client | `app/services/llm_service.py` | ~130 |
| Frontend | `angular-visitor/src/app/` (all .ts, .html, .scss) | ~2,000 |

**Total: ~3,300 lines of meaningful code.**
