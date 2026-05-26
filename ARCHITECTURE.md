# Architecture — ACE Reception Services

See **[CONTEXT.md](CONTEXT.md)** for the complete project overview including data model, API surface, AI flow, and file-by-file explanation.

## High-level

```
Visitor Browser
    │
    ▼
┌─────────────────────────────┐
│  Python FastAPI backend/    │  Single process, port 8000
│  • REST API                 │
│  • Auth (JWT)               │
│  • AI chat (LangGraph)      │
│  • Camera takeover (LiveKit)│
│  • Serves Angular SPA       │
└──────┬──────────┬───────────┘
       │          │
       ▼          ▼
  PostgreSQL   LiveKit
  (5433)       (7880)
```

## Directory Map

```
backend/          ★ The server — FastAPI app, all routes, models, auth, events, LiveKit tokens
app/              ★ AI library — LangGraph qualification graph, prompts, salon tools, LLM client
angular-visitor/  ★ Frontend — Angular 19 SPA with chat widget, video overlay, calendar picker
docker/           LiveKit server config
docs/             Specs and contracts (see CONTEXT.md for which are current vs legacy)
```

## Responsibility Split

### `backend/` — The Server (662 lines)
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
- LangGraph conversation graph: classify intent → route → generate reply
- Slovenian prompts per stage (greeting, discovery, availability, booking, handoff, idle)
- Deterministic salon tools (services list, availability, booking, staff request)
- OpenAI client wrapper (JSON, text, stream, tool calls)
- Runtime context builder from qualifier config

### `angular-visitor/` — Frontend (~1200 lines)
Angular 19 standalone SPA. Key components:
- **ReceptionistChatComponent** — Main chat UI with messages, input, action buttons
- **StaffVideoComponent** — LiveKit video overlay (polls live-session endpoint, renders remote video)
- **ServiceCardsComponent** — Service browsing cards
- **CalendarPickerComponent** — Date/time slot selection
- **HeaderComponent** — Salon name, open/closed status

Services:
- **SalonService** — Central state (messages, staffState, connection, send, poll)
- **ChatApiService** — HTTP layer with retry logic
