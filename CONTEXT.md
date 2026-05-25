# ACE Reception Services — Complete System Context

## Architecture
```
Browser → Java :8080 (serves Angular SPA + REST API)
Java → Python :8000 (AI qualifier runtime, via PythonQualifierRuntimeClient)
Java → PostgreSQL :5433 (all persistent data)
```

## Angular SPA (served from Java classpath, port 8080)

### Routes (`app.routes.ts`)
| Path | Component | Auth |
|---|---|---|
| `/admin` | AdminComponent | No (API calls require auth, 401 → redirect /login) |
| `/:slug/dashboard` | OrgDashboardComponent | No (API calls require auth) |
| `/:slug` | ReceptionistChatComponent | No (public) |
| `` | ReceptionistChatComponent | No (public) |

### App Shell (`app.component.ts`)
- Just `<router-outlet>` — routes render full-page components
- No shared layout between admin/chat/dashboard

### AdminComponent (`admin/admin.component.ts`)
- Fetches: GET /api/admin/organizations, GET /api/admin/users
- Creates: POST /api/admin/organizations, POST /api/admin/users
- State: orgs[], users[], error, form fields
- No SSE, no polling — static admin panel

### OrgDashboardComponent (`org-dashboard/org-dashboard.component.ts`)
- resolveOrg(): fetches /api/admin/organizations → finds org by slug → sets orgId
- loadLeads(): GET /api/organizations/{orgId}/leads → sorts (staffRequested first) → applyFilters()
- SSE: EventSource('/chat-events/stream?sid=*&tenantSlug={slug}')
  - onmessage: if event type matches, call loadLeads() + select(sid) if thread open
  - onerror: close + reconnect after 2s
- select(sid): GET /api/organizations/{orgId}/leads/{sid}/messages → messages[]
- sendTakeover(): POST /chat/staff {orgId, sid, text} → refresh
- endTakeover(): POST /api/organizations/{orgId}/leads/{sid}/takeover/end → refresh
- deleteLead(): DELETE /api/organizations/{orgId}/leads/{sid} → refresh
- State: leads[], allLeads[], messages[], selectedSid, takeoverActive, filters, activeTab
- Auto-refresh replaced by SSE (no setInterval)

### ReceptionistChatComponent (`receptionist-chat/`)
- Contains: HeaderComponent + ServiceCardsComponent + chat widget
- Uses SalonService for all state and API calls
- Template: message bubbles with role-based styling (ai/user/staff/system)

### SalonService (`services/salon.service.ts`)
- connect(): POST /chat → get sid → sessionStorage → loadHistory() → poll()
- loadHistory(): GET /api/public/orgs/{slug}/leads/{sid}/messages → messages[]
- poll(): SSE EventSource('/chat-events/stream?sid={sid}&tenantSlug={slug}')
  - onmessage: handle(event) — processes lead.takeover.started/ended, message.created
  - onerror: close + reconnect after 2s
- sendMessage(): POST /chat {sid, message, tenant_slug}
  - If staffState='connected': AI silent, no error
  - Else: show AI reply or survey step
- handle(event):
  - lead.takeover.started → staffState='connected'
  - lead.takeover.ended → staffState='idle', show AI resume
  - message.created:
    - staff: ALWAYS add (no dedup), staffState='connected'
    - assistant: add only if idle + not duplicate
- requestStaff(): POST /api/public/orgs/{slug}/leads/{sid}/request-staff → staffOffering()
- State: sid, staffState, messages[], connectionStatus

### ChatApiService (`services/chat-api.service.ts`)
- sendMessage(sid, msg): POST /chat {sid, message, tenant_slug} → ChatResponse
- getThread(sid): GET /api/public/orgs/{slug}/leads/{sid}/messages → MessageResponse[]
- pollEvents(sid, since): GET /chat-events/poll (HTTP long-poll, NOT used — SSE instead)
- Retry logic with exponential backoff on 5xx

---

## Java Backend (Spring Boot, port 8080)

### Key Controllers

**ChatApiController** — Main API for chat + takeover + events
| Endpoint | Method | Auth | What it does |
|---|---|---|---|
| /chat | POST | No | Visitor message → Python AI or survey |
| /chat/staff | POST | Yes | Staff takeover message → activates takeover, publishes events |
| /chat-events/poll | GET | No | HTTP long-poll for events |
| /chat-events/stream | GET | No | SSE stream for real-time events |
| /api/organizations/{id}/leads | GET | Yes | List leads for org |
| /api/organizations/{id}/leads/{sid}/messages | GET | Yes | Thread messages |
| /api/public/organizations/{slug}/leads/{sid}/messages | GET | No | Public thread |
| /api/public/organizations/{slug}/leads/{sid}/request-staff | POST | No | Mark lead as staff-requested |
| /api/organizations/{id}/leads/{sid}/takeover/end | POST | Yes | End takeover |

**AdminApiController** — REST endpoints for admin panel
| /api/admin/organizations | GET | Yes | List all orgs |
| /api/admin/organizations | POST | Yes | Create org |
| /api/admin/users | GET | Yes | List users |
| /api/admin/users | POST | Yes | Create user |

**PublicController** — Serves Angular SPA
- GET /, /demo, /admin, /admin/dashboard, /{slug}, /{slug}/dashboard → forward:/index.html

**OrganizationDashboardController** — DISABLED (Angular handles /{slug}/dashboard)

### Takeover Flow (Complete)

```
DASHBOARD (OrgDashboardComponent)
  sendTakeover()
    → POST /chat/staff {orgId, sid, text}

JAVA ChatApiController.staff()
  → takeoverService.startTakeover(lead, user, text)
    → leadService.activateTakeover(lead, user)  // sets takeoverActive=true, status=HUMAN_TAKEOVER
    → publish lead.takeover.started event (_seq=N)
    → conversationService.appendMessage(STAFF, text)
      → saves to conversation_messages table
      → publish message.created(staff) event (_seq=N+1)
      → publish lead.touched event (_seq=N+2)

SSE THREAD (background, polls every 500ms)
  leadEventService.fetchNow(orgId, sid, since, 50)
  → sends events to EventSource

VISITOR (SalonService)
  SSE onmessage → handle(event)
    1. lead.takeover.started → staffState='connected'
    2. message.created(staff) → add('staff', text)  // no dedup
    3. lead.touched → ignored (no handler)
```

### Event Types Published
| Event | Publisher | When |
|---|---|---|
| lead.takeover.started | TakeoverService | Staff starts takeover |
| lead.takeover.ended | TakeoverService | Staff ends takeover |
| message.created(user/assistant/staff) | ConversationService | Any message saved |
| lead.touched | ConversationService, ChatApiController | After message saved |
| lead.staff-requested | ChatApiController | Visitor clicks "Prosim osebje" |
| lead.profile.updated | ChatApiController | After qualifier evaluates |
| lead.qualified | ChatApiController | After qualifier evaluates |

### Data Model
**Lead** (leads table): sid, organization_id, status, takeover_active, staff_requested, last_message_preview, qualification_score, survey_progress, assigned_user_id

**ConversationMessage** (conversation_messages table): lead_id, organization_id, role (USER/ASSISTANT/STAFF), text, created_at

**LeadEvent** (lead_events table): organization_id, sid, event_type, payload_json, id (auto-increment = _seq)

---

## Known Issues & Edge Cases

1. **SSE initial burst**: SSE thread starts with since=0, dumps ALL historical events. Dashboard's onmessage calls loadLeads() for every event. With 1000 events, that's 1000 API calls. Mitigation: dashboard's loadLeads() replaces the full list (no append), so duplicates don't matter. But it's chatty.

2. **Staff message not appearing**: The handle() method now adds staff messages unconditionally (no dedup). This ensures they always render. But if loadHistory() already loaded them, they appear twice? No — loadHistory() calls this.messages.set() which REPLACES the array. SSE events arrive after and add to the array. No duplicates because loadHistory() set the array fresh, then SSE adds new messages on top.

3. **SSE reconnection**: onerror closes EventSource and reconnects after 2s. During reconnection gap, events might be missed. The thread starts with since=0, so it catches up. But it dumps ALL events again, which is wasteful.

4. **Deployment**: Angular builds to dist/angular-visitor/browser/. Must be copied to java-platform/target/classes/static/ BEFORE starting Java. Maven's process-resources copies src/main/resources/static/ to target/classes/static/. So files in src/main/resources/static/ get picked up automatically.

5. **Browser cache**: Content hashing ensures unique filenames per build. But if old main.js files remain in target/classes/static/, the browser's cached index.html might reference them. Clean old files on each deploy.
