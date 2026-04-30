# Events

## Purpose
Defines live event contracts for qualification updates, takeover, and video escalation.

These events are published via the existing event bus:
- `app/services/event_bus.py`
- exposed through `app/api/chat_events.py`

## Event Rules
1. Every event payload must include `sid` in the top-level envelope already produced by the event bus.
2. Payloads should be small, incremental, and UI-friendly.
3. Events should supplement persisted state, not replace it.
4. New events should not break existing dashboard listeners.

## Existing Relevant Events
Already in use or close to use:
- `message.created`
- `lead.touched`
- `survey.progress`
- `survey.completed`

## New Events To Add

---

## 1. `lead.profile.updated`
Published when structured lead profile changes.

Payload:
```json
{
  "profile": {
    "intent": "...",
    "timeline": "..."
  },
  "field_confidence": {
    "intent": 0.9,
    "timeline": 0.7
  },
  "confidence_overall": 0.82,
  "missing_fields": ["contact_phone"]
}
```

Use cases:
- dashboard updates visible lead details
- operator sees evolving qualification

---

## 2. `lead.qualified`
Published when score/band is computed or meaningfully changes.

Payload:
```json
{
  "qualification_score": 86,
  "qualification_band": "hot",
  "reasoning": "High intent with short timeline.",
  "recommended_next_action": "offer_human_takeover",
  "takeover_eligible": true,
  "video_offer_eligible": true,
  "confidence_overall": 0.82,
  "qualifier_id": 1,
  "qualifier_version": 3
}
```

Use cases:
- dashboard ranking update
- show hot/warm/cold segments
- trigger subtle takeover availability

---

## 3. `takeover.offered`
Published when human takeover becomes available.

Payload:
```json
{
  "mode": "text_or_video",
  "reason": "qualifier_hot_band",
  "video_offer_eligible": true
}
```

Use cases:
- chatbot shows non-intrusive CTA
- dashboard flags eligible lead

---

## 4. `takeover.accepted`
Published when visitor accepts takeover.

Payload:
```json
{
  "mode": "text",
  "accepted_via": "chat_cta"
}
```

Use cases:
- dashboard moves to active takeover state
- bot pauses

---

## 5. `video.offer.created`
Published when a video option is made available.

Payload:
```json
{
  "offer_origin": "qualifier",
  "rep_available": true,
  "cta_label": "Talk now",
  "expires_in_sec": 300
}
```

Use cases:
- chatbot shows floating pill/card
- dashboard shows pending offer state

---

## 6. `video.offer.dismissed`
Published when visitor dismisses the offer.

Payload:
```json
{
  "dismissed_by": "visitor"
}
```

Use cases:
- suppress repeated aggressive prompts

---

## 7. `video.room.ready`
Published when room/token is ready.

Payload:
```json
{
  "video_session_id": 77,
  "provider": "livekit",
  "room_id": "room_123",
  "status": "ready"
}
```

Use cases:
- operator join button becomes active
- visitor modal can proceed

---

## 8. `video.room.joined`
Published when either side joins.

Payload:
```json
{
  "video_session_id": 77,
  "joined_by": "rep",
  "status": "live"
}
```

Use cases:
- update UI presence state

---

## 9. `video.room.ended`
Published when the room ends.

Payload:
```json
{
  "video_session_id": 77,
  "ended_by": "rep",
  "reason": "completed",
  "fallback_to_chat": true
}
```

Use cases:
- return visitor to chat safely
- show post-call state in dashboard

---

## 10. `video.recording.started`
Payload:
```json
{
  "video_session_id": 77,
  "recording_status": "started"
}
```

---

## 11. `video.recording.stopped`
Payload:
```json
{
  "video_session_id": 77,
  "recording_status": "stopped"
}
```

---

## Dashboard Handling Notes
Primary file likely to update first:
- `frontend/manager-dashboard/src/app/app.component.ts`

New event handling should update:
- lead score/band
- explanation
- takeover availability
- video status badges/buttons

## Chatbot Handling Notes
Primary file likely to update first:
- `frontend/ACE-Chatbot/src/app/app.component.ts`

Chatbot should react to:
- `takeover.offered`
- `video.offer.created`
- `video.room.ready`
- `video.room.ended`

## Backward Compatibility
Do not remove current events.
Add new events alongside:
- `lead.touched`
- `message.created`

Where possible, continue publishing `lead.touched` for generic refresh behavior, while new events carry structured payloads.
