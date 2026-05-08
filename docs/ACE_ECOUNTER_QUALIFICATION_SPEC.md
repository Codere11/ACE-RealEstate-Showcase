# ACE e-Counter Qualification Funnel Spec

## Purpose
Redesign the AI Qualifier into a proper ACE e-Counter qualification engine.

## Current implementation note
The current runtime is intentionally minimal:
- fixed LangGraph flow: `interpret_turn -> decide_next_step -> persist`
- thin JSON-only LLM client
- dashboard edits qualification policy, not arbitrary graph topology

This document remains the broader product/funnel spec that should guide future expansion without reintroducing prompt spaghetti or heuristic routing as the primary logic.

The qualifier should not behave like a generic chatbot. It should behave like a controlled funnel that:
- routes the visitor correctly
- extracts only action-relevant facts
- keeps uncertainty explicit
- scores fit and intent deterministically
- chooses the right next step
- gives managers a trustworthy operating view

## Product framing
ACE e-Counter is a visitor-intake and conversion system with:
- survey intake
- open AI qualification chat
- manager dashboard visibility
- live help / human handoff
- payment-request workflow
- event-driven synchronization between visitor and operators

The qualifier therefore exists to support **operational decisions**, not just conversation quality.

---

## Success criteria
The qualifier is successful when it reliably does these five things:
1. **Route** the conversation into the correct path
2. **Understand** the visitor's context and intent
3. **Score** fit, urgency, and action-readiness
4. **Decide** the best next question or action
5. **Act** by handing off, collecting contact, offering demo/help, or soft-closing

## Non-goals
The qualifier is not meant to be:
- a general-purpose assistant
- an unrelated FAQ bot
- a freestyle autonomous agent
- a system that stores low-confidence guesses as facts

---

## Core design principles
1. **Conversation is the interface; qualification is the system.**
2. **Answer in scope, redirect out of scope.**
3. **Ask at most one useful follow-up at a time.**
4. **Stop asking once there is enough information to act.**
5. **Never store uncertain facts as if they were confirmed.**
6. **Managers should see evidence, not just scores.**
7. **Human handoff should happen at the right time, not the earliest time.**

---

## Top-level visitor routing
Before the lead enters the normal qualification funnel, classify the session into one of these visitor types:
- `sales_prospect`
- `existing_customer_support`
- `partner_or_vendor`
- `job_seeker`
- `irrelevant_or_joke`
- `abusive_or_spam`
- `unclear`

### Route actions
- `sales_prospect` → continue into qualification funnel
- `existing_customer_support` → support path / operator route
- `partner_or_vendor` → polite redirect
- `job_seeker` → polite redirect
- `irrelevant_or_joke` → redirect once, then soft-close if repeated
- `abusive_or_spam` → warn or close quickly
- `unclear` → ask one clarifying question

### Example
Input:
> "Pozdravljeni, prodajate sladoled?"

Expected result:
```json
{
  "visitor_type": "irrelevant_or_joke",
  "scope_status": "out_of_scope",
  "action": "redirect",
  "reason": "The message is unrelated to ACE e-Counter capabilities or business qualification."
}
```

---

## Funnel stages
### Stage 0 — Route
Goal:
- determine whether the conversation should enter qualification at all

Outputs:
- `visitor_type`
- `scope_status`
- `route_action`

### Stage 1 — Business context
Goal:
- understand the visitor and their organization at a high level

Target fields:
- `company_name`
- `contact_name`
- `role`
- `industry`
- `business_type`
- `website_url`
- `market_region`
- `team_size`

### Stage 2 — Current intake process
Goal:
- understand how they currently handle inbound visitors or leads

Target fields:
- `lead_sources`
- `monthly_inbound_volume`
- `current_response_process`
- `current_tools`
- `operator_team_exists`
- `survey_or_chat_today`

### Stage 3 — Pain discovery
Goal:
- understand what is not working today

Target fields:
- `main_pain_points`
- `response_speed_problem`
- `lead_quality_problem`
- `handoff_problem`
- `visibility_problem`
- `conversion_problem`

### Stage 4 — ACE capability fit
Goal:
- determine which ACE e-Counter capabilities actually match the need

Target fields:
- `needed_capabilities`
- `survey_fit`
- `open_chat_fit`
- `manager_dashboard_fit`
- `live_help_fit`
- `payment_request_fit`
- `multi_location_fit`

### Stage 5 — Commercial readiness
Goal:
- determine seriousness and timing

Target fields:
- `timeline`
- `urgency`
- `decision_maker`
- `budget_signal`
- `wants_demo`
- `wants_pricing`
- `wants_callback`
- `contact_capture_ready`

### Stage 6 — Action routing
Goal:
- stop over-qualifying and move the visitor to the best next action

Allowed actions:
- `continue_chat`
- `ask_one_more_question`
- `capture_contact`
- `offer_human_takeover`
- `offer_live_help`
- `offer_demo`
- `send_pricing_overview`
- `send_payment_request`
- `soft_close`
- `disqualify`

---

## Canonical lead profile
Recommended JSON shape for `LeadProfile.profile`:

```json
{
  "visitor_type": "sales_prospect",
  "company_name": "",
  "contact_name": "",
  "contact_email": "",
  "contact_phone": "",
  "website_url": "",
  "role": "",
  "decision_maker": null,
  "industry": "",
  "business_type": "",
  "team_size": "",
  "locations_count": null,
  "market_region": "",
  "lead_sources": [],
  "monthly_inbound_volume": "",
  "current_response_process": "",
  "current_tools": [],
  "operator_team_exists": null,
  "survey_or_chat_today": "",
  "main_pain_points": [],
  "response_speed_problem": null,
  "lead_quality_problem": null,
  "handoff_problem": null,
  "visibility_problem": null,
  "conversion_problem": null,
  "needed_capabilities": [],
  "survey_fit": null,
  "open_chat_fit": null,
  "manager_dashboard_fit": null,
  "live_help_fit": null,
  "payment_request_fit": null,
  "multi_location_fit": null,
  "timeline": "",
  "urgency": "",
  "budget_signal": "",
  "wants_demo": false,
  "wants_pricing": false,
  "wants_callback": false,
  "fit_status": "unknown",
  "disqualify_reason": "",
  "funnel_stage": "route",
  "qualification_complete": false
}
```

### Field rules
- unknown is allowed
- missing is not failure
- every extracted field should have confidence
- important fields should also carry evidence

### Evidence model
Recommended extension to `field_confidence` or adjacent metadata:

```json
{
  "monthly_inbound_volume": {
    "confidence": 0.84,
    "evidence": "We get around 70 inquiries per month.",
    "source_turn_index": 4
  }
}
```

---

## Scoring model
Scoring should be deterministic and backend-owned.

### Suggested weighted score
- `icp_fit`: 25
- `pain_intensity`: 20
- `capability_match`: 20
- `buying_intent`: 20
- `action_readiness`: 15

Total: 100

### Bands
- `hot`: 80-100
- `warm`: 55-79
- `cold`: 0-54
- `disqualified`: explicit route outcome, not just a low score

### Example scoring logic
#### ICP fit
Signals:
- has a real business
- has inbound traffic or inquiries
- needs intake / qualification / routing / handoff

#### Pain intensity
Signals:
- slow response
- too many junk leads
- manual qualification burden
- poor visibility into lead quality

#### Capability match
Signals:
- needs survey or open chat intake
- needs manager dashboard visibility
- needs human handoff or live help
- needs payment or next-step conversion workflow

#### Buying intent
Signals:
- requests demo
- requests pricing
- requests callback
- asks implementation questions

#### Action readiness
Signals:
- contactable
- near-term timeline
- decision-maker involved
- clear next step accepted

---

## Qualification completion rule
The system should not try to collect every possible field.

A lead is "qualified enough" when the system has enough information to act safely.

### Default completion heuristic
Mark `qualification_complete=true` when these are known with sufficient confidence:
- visitor type
- business context
- at least one real pain point
- at least one ACE capability match
- timeline or urgency signal
- a valid next action

If a commercial CTA is needed, contact details should also be present or explicitly requested.

---

## Runtime graph design
Use LangGraph-style controlled orchestration.

### Node 1 — `route_guard`
Inputs:
- latest message
- recent conversation window
- organization/product context

Outputs:
- `visitor_type`
- `scope_status`
- `route_action`
- `reason`

### Node 2 — `context_loader`
Loads:
- active qualifier config
- organization/product profile
- ACE e-Counter capability summary
- allowed/disallowed topic policy
- FAQ / pricing / support routing hints

### Node 3 — `fact_extractor`
Strict structured extraction only.

Outputs:
- `profile_patch`
- `field_confidence`
- `field_evidence`
- `confidence_overall`

### Node 4 — `profile_merger`
Deterministic backend merge rules:
- do not overwrite stronger facts with weaker guesses
- keep `unknown` explicit
- append or replace evidence only when stronger
- preserve source traceability
- detect contradictions

### Node 5 — `fit_scorer`
Outputs:
- `qualification_score`
- `qualification_band`
- `reasoning`
- `recommended_next_action`
- `takeover_eligible`
- `video_offer_eligible`

### Node 6 — `stage_planner`
Outputs:
- `funnel_stage`
- `next_best_question`
- `suggested_reply_strategy`
- `qualification_complete`

### Node 7 — `response_generator`
Rules:
- answer the user's in-scope question first when possible
- ask at most one useful follow-up
- never claim capabilities outside grounded ACE context
- if route action is redirect/close, do not answer unrelated content substantively

### Node 8 — `persist_and_emit`
Persists:
- `LeadProfile`
- `QualifierRun`

Emits:
- `lead.profile.updated`
- `lead.qualified`
- `takeover.offered` when relevant
- existing generic refresh events as needed

---

## Prompting policy
Use separate prompts per node.

### Do not use
- one giant general system prompt
- open-ended autonomous agent loops

### Do use
- narrow routing prompt
- narrow extraction prompt
- deterministic scoring logic in Python/backend
- constrained response prompt

### Response-generation policy
The response generator must obey:
- do not pretend ACE offers unrelated services
- do not store unconfirmed assumptions as facts
- do not ask repeated questions for already-known facts
- prefer concise, professional, action-oriented replies
- when enough info exists, move to CTA instead of more discovery

---

## Out-of-scope / heckler handling
### Strike policy
Track per session:
- `out_of_scope_count`
- `abuse_count`
- `last_route_action`

### Default behavior
- first irrelevant message → polite redirect
- second irrelevant message → firmer redirect
- third irrelevant message → soft close
- severe abuse/spam → immediate close

### Example redirect reply
> ACE e-Counter is a visitor-intake and qualification system, so I cannot help with that topic. If you want, I can quickly check whether ACE e-Counter is a fit for your business and workflow.

---

## Manager dashboard requirements
Managers should see more than score.

### Must show
- `visitor_type`
- `funnel_stage`
- `qualification_score`
- `qualification_band`
- `confidence_overall`
- `reasoning`
- `recommended_next_action`
- `missing_fields`
- `disqualify_reason`
- field-level evidence for important conclusions

### Should show
- qualification completeness
- contradiction warnings
- handoff eligibility
- live-help eligibility
- CTA recommendation priority

---

## Event and contract additions
Current contracts are already close.

Recommended additions:
- persist `visitor_type`
- persist `funnel_stage`
- persist `qualification_complete`
- persist `disqualify_reason`
- attach evidence metadata for important fields

### Event payload suggestions
`lead.profile.updated` should optionally include:
```json
{
  "visitor_type": "sales_prospect",
  "funnel_stage": "pain_discovery",
  "qualification_complete": false,
  "profile": {},
  "field_confidence": {},
  "missing_fields": []
}
```

`lead.qualified` should optionally include:
```json
{
  "qualification_score": 83,
  "qualification_band": "hot",
  "reasoning": "Clear workflow pain, strong capability match, and demo intent.",
  "recommended_next_action": "offer_human_takeover",
  "takeover_eligible": true,
  "video_offer_eligible": false,
  "visitor_type": "sales_prospect",
  "funnel_stage": "action_routing"
}
```

---

## Evaluation harness
Qualification quality must be tested with a replayable transcript set.

### Required eval buckets
1. obvious good prospects
2. ambiguous prospects
3. irrelevant/joke traffic
4. abusive/spam traffic
5. support requests
6. partner/vendor/job-seeker traffic
7. multilingual or vague inputs
8. contradictory-information conversations

### Evaluate for
- routing accuracy
- extraction accuracy
- confidence calibration
- unnecessary-question rate
- scoring quality
- next-action quality
- escalation timing
- false-positive handoff rate

---

## Rollout plan
### Phase 1
- introduce `visitor_type`, `funnel_stage`, `qualification_complete`, `disqualify_reason`
- add `route_guard`
- keep current extract/score/reply path behind it

### Phase 2
- add evidence-aware extraction + deterministic profile merge
- update dashboard to show stage/evidence/missing fields

### Phase 3
- add stage planner and stronger CTA routing
- refine takeover/live-help offer logic

### Phase 4
- add transcript-based evaluation suite
- tune scoring weights and thresholds from observed data

---

## Final design rule
ACE e-Counter should behave like this:

> Quickly determine whether the visitor is relevant, extract only the facts needed to act, keep uncertainty explicit, and move the right people to the right next step with minimal friction.
