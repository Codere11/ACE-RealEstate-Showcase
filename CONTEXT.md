# ACE — Project Context

AI SDR platform. Chat widget qualifies B2B visitors, books instant video meetings, formats meeting notes into lead cards.

## Architecture

```
Visitor Browser → FastAPI (port 8000) → PostgreSQL (5433) + LiveKit (7880)
```

Single Python process. `backend/` is the server. `app/` is an AI library imported directly.

## Directory Map

```
backend/                  Server — FastAPI, routes, auth, events, LiveKit tokens
app/                      AI library — LangGraph graph, B2B tools, LLM client
angular-visitor/          Angular 19 SPA — chat widget, video overlay, dashboard
docker/                   LiveKit config
docs/                     Additional specs
scripts/                  B2B simulator, demo data
```

## Data Model

| Table | Purpose |
|---|---|
| organizations | B2B company (tenant) |
| users | Auth (PLATFORM_ADMIN, ORG_ADMIN, ORG_USER) |
| leads | Visitor session: sid, status, takeover_active, qualifier_profile |
| conversation_messages | Chat history (user/assistant/staff) |
| lead_events | Event log for polling |
| qualifiers | AI behavior config per org |
| bookings | Scheduled discovery calls |

SID: `sid_` + 12 hex chars. LeadStatus: OPEN_CHAT, HUMAN_TAKEOVER, CLOSED.

## API

### Public
| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Visitor message → AI reply |
| POST | `/chat/stream` | SSE streaming |
| GET | `/chat-events/poll` | Real-time events |
| GET | `/api/public/organizations/{slug}/live-session` | Check if video is live |
| POST | `/login` | Form login → JWT |

### Authenticated (JWT)
| Method | Path | Purpose |
|---|---|---|
| POST | `/chat/staff` | Staff takeover message |
| GET | `/api/organizations/{id}/leads` | Lead list with profiles |
| GET | `/api/organizations/{id}/leads/{sid}/messages` | Chat history |
| POST | `/api/organizations/{id}/leads/{sid}/takeover/end` | End takeover |
| DELETE | `/api/organizations/{id}/leads/{sid}` | Delete lead |
| POST | `/api/organizations/{id}/live-sessions/go-live` | Start video |
| POST | `/api/organizations/{id}/live-sessions/end` | End video |
| POST | `/api/organizations/{id}/leads/{sid}/meeting-notes` | Save & format notes |
| GET/POST | `/api/organizations/{id}/bookings` | Booking CRUD |

## AI Flow

```
Visitor sends message
  → Save to DB
  → Load qualifier + recent messages
  → LangGraph: build prompt → run tools → generate reply
  → Extract profile fields (regex + LLM)
  → Return reply
```

### B2B Tools (app/qualification/tools.py)
- `ace_get_context` — Open/closed status, working hours
- `ace_check_contact` — Has visitor provided phone/email?
- `ace_schedule_call` — Book 30-min discovery call
- `ace_request_team` — Request live team takeover
- `ace_update_profile` — Record business_name, budget, problem, etc.

### Turn-Based Behavior
| Turn | Instruction |
|---|---|
| 0 | Greet, ask what brought them |
| 1 | If lead has budget/problem → offer instant team takeover |
| 2 | If no to instant → schedule call |
| 3+ | Close, ask for email/phone |

## Video Handoff

```
Staff: goLive() → LiveKit room → publish video+audio
Visitor: receives event → consent prompt → accept → connect → two-way video
End: staff calls endLive() → meeting notes popup → save → formatted on lead card
```

Both sides: full-size video, self-PIP, mic/camera/minimize/hangup controls. Minimize shrinks to corner PIP.

## Meeting Notes

1. Staff ends live session → popup appears
2. Types shorthand notes in any language
3. Backend sends raw notes + chat history + lead profile to LLM
4. LLM returns formatted summary in same language
5. Saved to lead profile, displayed on lead card

## Lead Cards

Dashboard tab "LEAD CARDS" shows all leads as cards with:
- Qualification score (hot/warm/cold)
- Business name, contact name
- 📞 Phone, ✉️ Email (actual values)
- Budget, Problem, Industry
- Status, message count, meeting time
- Click → detail view with profile, conversation, meeting notes

## Seeding

First startup auto-creates:
- Demo org (`slug: demo`, `name: ACE`)
- Admin user (`admin`/`test123`)
- Default qualifier ("AI Svetovalec")

## Key Design Decisions

1. Single process — `backend/` is everything, `app/` is a library
2. Direct import — no HTTP between services
3. Turn-based AI — prompt changes per conversation turn
4. Deterministic tools — LLM chooses tools, tool outputs are real (DB writes)
5. Polling for events — frontend polls every 1s, WebSocket for internal pub/sub
6. Video via LiveKit — two-way, consent-gated
7. SID-based sessions — visitors don't log in
8. Any-language meeting notes — LLM mirrors input language

## Environment

```
OPENAI_API_KEY=sk-...
ACE_LLM_PROVIDER=openai|deepseek
ACE_LLM_MODEL=gpt-4.1-mini
DATABASE_URL=postgresql://ace_user:test_password_123@localhost:5433/ace_platform
ACE_LIVEKIT_WS_URL=ws://localhost:7880
ACE_LIVEKIT_API_KEY=devkey
ACE_LIVEKIT_API_SECRET=devsecretkey_for_local_livekit_32chars
ACE_SECRET=...
```
