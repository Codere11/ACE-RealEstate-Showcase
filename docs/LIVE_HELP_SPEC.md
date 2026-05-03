# Live Help Spec

## Purpose
Add the first proper implementation slice for one-way live help inside ACE e-Counter.

This feature is **not** a two-way video call yet.
For the visitor, it behaves like a staff member stepping in live:
- visitor camera stays off
- visitor microphone stays off
- no browser permission prompt is required on the visitor side
- the visitor keeps chatting normally below the video area

## Product intent
Live help should feel like a real counter or store interaction:
- the visitor starts with ACE e-Counter
- a staff member can prepare to step in
- the staff member can go live above the conversation
- the visitor sees live help in the existing top rectangle

## Rectangle placement
### Visitor
- use the existing top rectangle in the chatbot
- states: `idle -> joining -> live -> ended`

### Manager dashboard
- use the top centered rectangle above the filter/overview area
- states: `idle -> preview -> live -> ended`

## First implementation slice
The first slice is intentionally transport-agnostic.
It should prove:
- session model
- manager controls
- visitor state transitions
- live event flow
- backend session persistence

It does **not** need real media transport yet.

## Phase 1 scope
### Backend
- add `LiveSession` DB model
- add manager org routes
- add public visitor route
- emit live session events

### Manager UI
- top centered live-help stage
- `Start preview`
- `Go live`
- `End live`
- target lead indicator

### Visitor UI
- top rectangle reacts to live-help events
- joining state
- live state
- ended state

## Deferred from Phase 1
- actual camera capture
- actual video/audio transport
- LiveKit integration
- reconnect logic tied to media tracks
- mute/unmute controls tied to real audio

## Session model
### LiveSession
Suggested fields:
- `id`
- `organization_id`
- `sid`
- `manager_user_id`
- `manager_display_name`
- `provider`
- `status`
- `room_name`
- `stage_message`
- `started_at`
- `live_at`
- `ended_at`
- `created_at`
- `updated_at`

### Status values
- `preview`
- `live`
- `ended`
- `disconnected`

## API
### Manager routes
- `GET /api/organizations/{org_id}/live-sessions/current?sid=...`
- `POST /api/organizations/{org_id}/live-sessions/preview`
- `POST /api/organizations/{org_id}/live-sessions/go-live`
- `POST /api/organizations/{org_id}/live-sessions/{session_id}/end`

### Public visitor route
- `GET /api/public/organizations/{org_slug}/live-session?sid=...`

## Events
The first slice should emit:
- `live_session.live`
- `live_session.ended`

Optional later:
- `live_session.preview_ready`
- `live_session.disconnected`

## Manager UX states
### Idle
- black rectangle
- no active live session

### Preview
- black rectangle remains for now
- manager has prepared the live-help stage
- target lead is shown below

### Live
- rectangle remains stage placeholder for now
- state badge shows live
- visitor receives live event

### Ended
- returns to idle shell

## Visitor UX states
### Idle
- black rectangle only

### Joining
- subtle message in the rectangle
- example: `<Agent name> is joining to help`

### Live
- first slice shows live state in the rectangle
- later this will be replaced with real one-way video

### Ended
- short ended state
- then return to idle

## Build order
1. add spec
2. add backend `LiveSession` model + schemas + service + routes
3. wire manager dashboard controls to backend
4. wire visitor rectangle to public state + live events
5. verify state flow locally
6. only then add LiveKit transport

## Transport decision for later
Recommended later transport layer:
- **LiveKit**, self-hosted locally first

Reason:
- no paid service required to begin
- custom UI stays fully ours
- can start one-way and expand later
