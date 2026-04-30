# Video Takeover Spec

## Purpose
Extend the existing takeover system so that high-intent or explicitly requesting visitors can transition from chat to a live video call in a **gentle, non-intrusive** way.

This is not a popup-first feature. It is a trust-building escalation path.

## UX Principles
1. No forced interruption of chat.
2. No auto-opening video modals.
3. No automatic visitor camera/mic activation.
4. Video offer appears only when relevant.
5. Visitor can ignore the offer and continue chatting normally.
6. Operator receives chat history and profile context before joining.

## Trigger Conditions
Video takeover may be offered when:
- visitor explicitly asks for a human or live call
- qualifier marks `takeover_eligible = true`
- qualifier marks `video_offer_eligible = true`
- operator manually offers video from dashboard

## Non-Intrusive UI Definition
"Non-intrusive" means:
- show a subtle floating CTA or inline card
- do not block the current conversation
- no full-screen takeover
- no modal until visitor actively clicks
- if ignored, it remains available but quiet

## Current Reusable Base
Existing pieces:
- `app/services/takeover.py`
- `/skip_to_human` path in `app/api/chat.py`
- dashboard takeover UI in `frontend/manager-dashboard/src/app/app.component.*`
- live events via `app/services/event_bus.py` and `app/api/chat_events.py`

## Source of Truth
### Runtime source of truth
- video room/session state should be explicit
- linked by `sid`
- ideally DB-backed when implemented fully

### Temporary acceptable state for MVP
- in-memory room/session registry is acceptable for first iteration
- but event contracts must still be stable

## Main Entities
### TakeoverState
Tracks whether human takeover is:
- inactive
- text-enabled
- video-offered
- video-pending
- video-live
- ended

### VideoSession
Tracks:
- `sid`
- provider
- room id
- room url/token
- rep id
- status
- offered_at
- accepted_at
- ended_at
- recording consent/status

## Provider Recommendation
Use one of:
- LiveKit
- Daily
- Twilio Video

### Recommended starting choice
**LiveKit** or **Daily**
- both are practical
- both support tokenized room access
- both are better suited than building WebRTC from scratch

## Room Flow
1. qualifier or operator decides video is relevant
2. backend publishes `video.offer.created`
3. chatbot shows subtle offer
4. visitor clicks accept
5. backend creates room/token
6. backend publishes `video.room.ready`
7. operator sees join state in dashboard
8. visitor joins with camera/mic off by default
9. operator joins with chat/profile context
10. room ends, state stored on lead/session

## Visitor Flow
### Offer state
Visitor sees one of:
- inline prompt below assistant message
- floating pill/button

### Click behavior
Clicking the CTA opens a small modal or panel:
- short explanation
- rep availability
- camera/mic remains off by default
- explicit join button required

### Fallbacks
If visitor declines or closes:
- continue in chat
- optionally offer audio-only later

## Operator Flow
Dashboard should support:
- `Offer Video`
- `Join Video`
- `Continue in Chat`
- visibility into room status
- pre-join context panel

Required pre-join context:
- recent chat transcript
- structured lead profile
- qualifier explanation
- confidence/score

## Recording Rules
Recording must be:
- opt-in
- explicit
- provider-supported
- stored against session/lead metadata

If recording is enabled, store:
- consent timestamp
- recording id/reference
- recording status

## Backend Changes
## Must add
Create:
- `app/services/video_service.py`
- `app/api/video.py`

### Must modify
- `app/services/takeover.py`
- `app/api/chat.py`
- `app/main.py`

## Suggested endpoints
- `POST /video/offer`
- `POST /video/accept`
- `POST /video/decline`
- `POST /video/join`
- `POST /video/end`
- `POST /video/webhook` (provider callbacks)

## Frontend Changes
### Chatbot
Modify:
- `frontend/ACE-Chatbot/src/app/app.component.ts`
- `frontend/ACE-Chatbot/src/app/app.component.html`

Optional new components:
- `video-offer.component.ts`
- `video-preview-modal.component.ts`

### Dashboard
Modify:
- `frontend/manager-dashboard/src/app/app.component.ts`
- `frontend/manager-dashboard/src/app/app.component.html`

Optional new components:
- `video-join-panel.component.ts`
- `video-status-badge.component.ts`

## Event Requirements
Video takeover must use live events.
At minimum:
- `takeover.offered`
- `takeover.accepted`
- `video.offer.created`
- `video.offer.dismissed`
- `video.room.ready`
- `video.room.joined`
- `video.room.ended`
- `video.recording.started`
- `video.recording.stopped`

## Interaction With Existing Takeover
Text takeover remains the base layer.

Rules:
- text takeover can happen without video
- video takeover implies human takeover
- if video fails, stay in human text takeover
- visitor should never lose the ability to continue chatting

## MVP Scope
MVP should support:
- operator manual video offer
- visitor explicit acceptance
- room creation via provider
- chat context visible to operator
- fallback to text takeover

## Deferred Scope
Can wait until later:
- recording
- screen share
- scheduling if unavailable
- audio-only dedicated mode
- provider analytics sync

## Testing Requirements
Add tests for:
- offer eligibility
- accept/decline behavior
- room creation path
- fallback when provider fails
- event emission
- human takeover remains active when video fails
