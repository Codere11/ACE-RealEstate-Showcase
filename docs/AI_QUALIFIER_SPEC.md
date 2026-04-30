# AI Qualifier Spec

## Status
### Implemented first step (2026-04-30)
The current implementation now supports a real, manager-driven qualifier flow instead of forcing users into the survey first.

Implemented now:
- DB-backed `Qualifier`, `LeadProfile`, and `QualifierRun`
- qualifier CRUD + publish/archive lifecycle
- public active-qualifier detection per organization
- chatbot entry-mode switch: when a live qualifier exists, chat starts in open free-text mode
- manager dashboard qualifier management UI
- manager lead-profile visibility with score / confidence / reasoning / takeover flags
- LLM-backed structured extraction
- deterministic scoring / banding / takeover decisions
- LLM-backed assistant reply generation
- lightweight LangGraph runtime with `extract -> score -> reply`

Not implemented yet:
- grounded listing/inventory retrieval
- true video takeover flow
- richer graph branches / retrieval tools / AB testing

## Purpose
Add a tenant-scoped, DB-backed AI qualifier that can be created, edited, published, and archived similarly to surveys, but is a separate system.

The qualifier must feel effortless for the visitor:
- minimal friction
- mostly free-text conversation
- quick replies only as optional accelerators
- structured lead understanding updated continuously in the background
- manager sees score, confidence, explanation, and takeover eligibility in real time

## Product Intent
The AI qualifier is not a rigid form replacement. It is a live conversation intelligence layer that:
1. extracts lead intent and key facts from chat
2. scores lead quality continuously
3. decides whether human takeover should be offered
4. optionally uses tenant knowledge to answer accurately
5. persists structured profile data for operators and analytics

## Core UX Principles
1. User should be able to type naturally.
2. Do not force form-like interrogation unless required.
3. Ask only for missing information that materially improves qualification.
4. Re-use known facts instead of asking twice.
5. Escalate gently when confidence and intent are high.
6. If confidence is low, ask one smart clarifying question instead of dumping a long questionnaire.

## Recommendation: LangGraph vs LangChain
### Recommended
Use **LangGraph** for runtime orchestration.

Why:
- the qualifier is stateful across turns
- it needs deterministic steps
- it may call multiple tools/services (retrieval, extraction, scoring, escalation)
- it must remain debuggable and safe
- it fits publishable qualifier configs better than a loose chain

### Optional
Use **LangChain Core** utilities only where helpful:
- prompt templates
- model wrappers
- message abstractions
- structured output adapters

### Avoid
Do not build a fully open-ended agent loop for qualification. Qualification should be a **controlled graph**, not an autonomous agent.

## System Boundaries
### Source of truth
- Qualifier config: database
- Active qualifier per tenant: database
- Lead profile: database
- Runtime UI hints: API response + live events
- Temporary memory during chat turn: runtime only

### Not source of truth
- `data/conversation_flow.json`
- in-memory-only lead fields
- notes-only storage for qualification results

## Main Entities
### Qualifier
Tenant-owned configuration that defines:
- extraction fields
- prompt / behavior rules
- scoring thresholds
- confidence thresholds
- takeover rules
- optional retrieval sources
- enabled features
- status (`draft`, `live`, `archived`)

### Lead Profile
Structured output produced by the active qualifier for a conversation/session.

### Qualifier Run
Audit record of one qualifier execution against a session or message window.

## Qualifier Lifecycle
Qualifier status mirrors survey lifecycle:
- `draft`: editable, not used by production chat
- `live`: active for runtime qualification
- `archived`: frozen, not active

Rules:
- only one `live` qualifier per organization for now
- editing a `live` qualifier should create a new draft or require archive-first
- every stored lead profile should reference qualifier version used

## Runtime Behavior
## Trigger points
The qualifier runs:
- on first meaningful user message
- after each user message
- after explicit contact submission
- before takeover offer decision

## Runtime graph (recommended LangGraph shape)
### Current implemented graph
1. **Extract**
   - collect recent chat window
   - combine heuristic extraction with LLM structured extraction
   - merge partial fields into the stored lead profile
   - store field-level confidence and reasoning hints
2. **Score**
   - apply deterministic scoring rules / thresholds
   - compute `qualification_score`
   - compute `band` (`hot`, `warm`, `cold`)
   - compute `takeover_eligible` and `video_offer_eligible`
   - determine missing required fields and recommended next action
3. **Reply**
   - generate the next assistant response with the LLM
   - use qualifier config, recent conversation, known profile, missing fields, and takeover state
   - answer the user's message first when possible
   - ask at most one useful follow-up when more information is needed
4. **Persist + emit events**
   - save lead profile
   - save qualifier run audit
   - publish live events

### Next graph extension
Optional next nodes can be inserted cleanly before reply generation:
- **Retrieve tenant context** for grounded availability / listing / FAQ answers
- **Offer takeover** for non-intrusive human escalation
- **Offer video** when the qualifier and lead state justify it

## Effortless User Experience Requirements
The qualifier must optimize for low friction:
- No mandatory long survey before value is given.
- Contact details should be requested only when timing is right or when intent is strong.
- If user asks a question, answer it first when possible.
- Clarifying questions should be short and singular.
- If quick replies are shown, they must be optional and skippable.
- The system should infer from conversation whenever possible.

### Good example behavior
User: "I need help with my situation and want to know if this is a fit."
System:
- extracts broad intent
- answers at a high level
- asks only the most useful next question
- avoids forcing a full structured questionnaire immediately

## Qualifier Config Shape
A qualifier config should contain at least:
- `name`
- `slug`
- `status`
- `system_prompt`
- `assistant_style`
- `goal_definition`
- `field_schema`
- `required_fields`
- `scoring_rules`
- `band_thresholds`
- `confidence_thresholds`
- `takeover_rules`
- `video_offer_rules`
- `rag_enabled`
- `knowledge_source_ids`
- `max_clarifying_questions`
- `contact_capture_policy`
- `version_notes`

## Required Output From Qualifier
Each run should produce:
- structured `lead_profile`
- `qualification_score` (0-100)
- `qualification_band`
- `confidence_overall` (0-1)
- field-level confidence map
- short operator explanation
- short user-safe summary if needed
- `takeover_eligible`
- `video_offer_eligible`
- `next_best_question` (optional)
- `suggested_reply_strategy`

## Persistence Requirements
## New backend models to add
File: `app/models/orm.py`

Add models:
- `Qualifier`
- `LeadProfile`
- `QualifierRun`

Optional later:
- `KnowledgeDocument`
- `KnowledgeChunk`

## New API schemas
File: `app/models/schemas.py`

Add:
- `QualifierCreate`
- `QualifierUpdate`
- `QualifierResponse`
- `LeadProfileResponse`
- `QualifierRunResponse`

## New backend services
Create:
- `app/services/llm_service.py`
- `app/services/qualifier_service.py`
- optional: `app/services/rag_service.py`

## New API router
Create:
- `app/api/qualifiers.py`

Routes should mirror surveys:
- `GET /api/organizations/{org_id}/qualifiers`
- `POST /api/organizations/{org_id}/qualifiers`
- `GET /api/organizations/{org_id}/qualifiers/{qualifier_id}`
- `PUT /api/organizations/{org_id}/qualifiers/{qualifier_id}`
- `POST /api/organizations/{org_id}/qualifiers/{qualifier_id}/publish`
- `POST /api/organizations/{org_id}/qualifiers/{qualifier_id}/archive`
- optional: `GET /api/organizations/{org_id}/qualifiers/{qualifier_id}/runs`

## Runtime integration points
### Must modify
- `app/api/chat.py`
- `app/main.py`
- `frontend/manager-dashboard/src/app/app.component.ts`
- `frontend/manager-dashboard/src/app/app.component.html`
- `frontend/manager-dashboard/src/app/services/dashboard.service.ts`

### Add dashboard qualifier management
Create:
- `frontend/manager-dashboard/src/app/models/qualifier.model.ts`
- `frontend/manager-dashboard/src/app/services/qualifiers.service.ts`
- `frontend/manager-dashboard/src/app/qualifiers/qualifier-list.component.ts`
- `frontend/manager-dashboard/src/app/qualifiers/qualifier-editor.component.ts`

## Editor Design Recommendation
Do **not** copy the survey node-builder literally.

Better approach:
- configuration form for prompt/behavior
- editable field schema list
- threshold sliders/inputs
- takeover rules editor
- optional example conversation tests

Reason:
A qualifier is closer to a typed policy/configuration system than a pure survey flow.

### Current dashboard editor shape
The current dashboard implementation is intentionally manager-friendly and keeps the structure simple:
- **Name / slug**
- **How should the agent sound?**
- **What should the agent achieve?**
- **Core instructions for the agent**
- **What should the agent capture?**
  - field name
  - field type
  - required / optional
- advanced settings for:
  - confidence thresholds
  - takeover rules
  - video-offer rules
  - scoring rules
  - generated field schema preview

This keeps the manager in control without requiring a giant spaghetti prompt.

## MVP Runtime Rules
For MVP:
- one active qualifier per organization
- one default model per active qualifier
- one structured output schema
- one qualification score
- one takeover/video decision path

## Guardrails
- no silent hallucinated facts in stored profile
- every extracted field should allow `unknown`
- confidence below threshold should not be treated as fact
- user-facing claims should be grounded in chat or retrieval context
- qualifier must not spam clarifying questions
- if visitor explicitly requests human help, set takeover eligibility immediately

## Testing Requirements
Add tests for:
- qualifier CRUD lifecycle
- only one live qualifier per org
- structured extraction merge behavior
- confidence threshold behavior
- takeover eligibility trigger
- video-offer eligibility trigger
- chat runtime remains functional when no live qualifier exists

## Rollout Plan
Phase 1:
- DB models
- CRUD API
- dashboard editor
- chat integration with mocked/deterministic qualifier
- ✅ completed

Phase 2:
- LLM structured extraction
- field confidence
- explanations
- event-driven dashboard updates
- LLM-generated assistant replies
- lightweight LangGraph orchestration
- ✅ mostly completed as the current first production-ready step

Phase 3:
- optional retrieval
- richer analytics
- non-intrusive takeover/video offer flow
- A/B qualifier testing if needed
