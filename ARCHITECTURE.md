# Architecture — ACE

See **[CONTEXT.md](CONTEXT.md)** for the complete project overview including data model, API surface, AI flow, and file-by-file explanation.

## High-level

```
Visitor Browser
    │
    ▼
┌─────────────────────────────────┐
│  Python FastAPI backend/        │  Single process, port 8000
│  • REST API                     │
│  • Auth (JWT)                   │
│  • AI qualification (LangGraph) │
│  • Video takeover (LiveKit)     │
│  • Serves Angular SPA           │
└──────┬──────────┬───────────────┘
       │          │
       ▼          ▼
  PostgreSQL   LiveKit
  (5433)       (7880)
```

## Directory Map

```
backend/          ★ The server — FastAPI app, all routes, models, auth, events, LiveKit tokens
app/              ★ AI library — LangGraph qualification graph, B2B tools, LLM client
angular-visitor/  ★ Frontend — Angular 19 SPA with chat widget, video overlay, booking timeline
docker/           LiveKit server config
docs/             Specs and contracts
scripts/          B2B conversation simulator, demo data seeding
```

## Responsibility Split

### `backend/` — The Server (~700 lines)
Everything the visitor or dashboard needs:
- REST API (`routes_chat.py`, `routes_admin.py`)
- Auth with JWT (`auth.py`)
- Async PostgreSQL via SQLAlchemy (`models.py`, `database.py`)
- Event pub/sub with WebSocket fanout (`events.py`)
- LiveKit token generation (`livekit_token.py`)
- Auto-seeds demo org, admin user, qualifier on first start (`main.py`)
- Serves built Angular SPA from `static/`

### `app/` — AI Library (~550 lines)
Imported directly by `backend/routes_chat.py`. No separate process.
- LangGraph conversation flow: build prompt → run tools → generate reply
- Turn-based system prompt (aggressive takeover push on turn 1)
- B2B tools (get_context, check_contact, schedule_call, request_team, update_profile)
- OpenAI client wrapper (JSON, text, stream, tool calls)
- Runtime context builder from qualifier config

### `angular-visitor/` — Frontend (~1,200 lines)
Angular 19 standalone SPA. Key components:
- **ReceptionistChatComponent** — Main chat UI with messages, input, action buttons
- **StaffVideoComponent** — LiveKit video overlay (16:9, fade-in)
- **CalendarPickerComponent** — Date/time slot selection for discovery calls
- **HeaderComponent** — Status bar (open/closed)
- **OrgDashboardComponent** — 3-tab dashboard: conversations, AI qualifier editor, bookings

Services:
- **SalonService** — Central state (messages, staffState, connection, send, poll)
- **ChatApiService** — HTTP layer with retry logic
