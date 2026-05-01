# Product Overview

## What ACE Real Estate is
ACE Real Estate is a multi-tenant lead qualification and conversion system for real-estate teams.

It combines:
- a visitor-facing chatbot/survey UI
- a manager dashboard
- AI-assisted qualification
- live lead updates
- payment request flow

The project is designed to demonstrate a coherent product, not a collection of disconnected features.

---

## Core product problem
Real-estate teams often have to juggle:
- slow manual lead qualification
- low-context contact forms
- fragmented follow-up tools
- weak visibility into which leads are actually worth pursuing

That creates two failures:
1. **the visitor experience is clumsy**
2. **the manager side lacks decision-quality data**

---

## Product thesis
The product thesis is simple:

> Let visitors talk naturally, qualify them in the background, give managers clear lead-quality visibility, and make the next business step actionable.

That is why the product is built around four connected layers.

---

## 1. Visitor intake layer
### Why it exists
Visitors should not be forced into a rigid process too early.

### What it does
Depending on tenant configuration, the chatbot can start in:
- **survey mode** for structured intake
- **open AI qualifier mode** for natural free-text conversation

### Why this matters
This lets the system adapt to different org preferences without changing code for each tenant.

---

## 2. AI qualification layer
### Why it exists
A chat experience alone is not enough; the business side needs structured signal.

### What it does
The qualifier:
- extracts lead facts from conversation
- updates a structured lead profile
- scores the lead deterministically
- assigns a hot/warm/cold band
- explains why the score is what it is

### Why this matters
Managers need something more useful than “the bot had a chat.”
They need:
- quality
- confidence
- reasoning
- next-step guidance

---

## 3. Manager operations layer
### Why it exists
If the system does not help the operator act, it is just an intake toy.

### What it does
The dashboard lets managers:
- inspect leads
- review qualification output
- configure the qualifier
- take over chat
- send payment requests

### Why this matters
This turns the system into an operational tool instead of a passive form/chat frontend.

---

## 4. Conversion layer
### Why it exists
Qualification should lead to a real business action.

### What it does
The payment request flow allows the manager to:
- create a payment request
- send it directly into chat
- open a hosted checkout flow for the visitor
- track sent/paid state

### Why this matters
This closes the loop from:
- visitor interest
- to qualification
- to manager action
- to conversion

---

## Why payments are currently designed this way
For the current stage of the project:
- the UX should stay simple
- the payment path should stay trustworthy
- the code should stay easy to evolve into a real SaaS integration later

So the project uses:
- **hosted Stripe Checkout**, not a custom card form
- **organization-level Stripe Connect settings**, not tenant key-pasting UX
- a **demoable Stripe-hosted fallback** when a connected account is not fully ready yet

That keeps the current flow usable while preserving the right long-term architecture.

---

## Current coherent demo story
A coherent demo of the product should look like this:

1. visitor opens chatbot
2. qualifier runs in open chat mode
3. manager sees lead quality in dashboard
4. manager sends payment request
5. visitor opens hosted checkout
6. payment status comes back into the system

That is the clearest current business story the product supports.

---

## What is intentionally unfinished
Some things are intentionally not claimed as finished yet:
- grounded listing retrieval
- full video takeover workflow
- polished production-grade Stripe Connect onboarding for live clients
- deeper analytics/reporting

That is deliberate.
The goal is to keep the current feature set coherent rather than pretending everything is done.

---

## Where to read next
- Local setup: `docs/LOCAL_DEVELOPMENT.md`
- API overview: `docs/API_OVERVIEW.md`
- AI qualifier design: `docs/AI_QUALIFIER_SPEC.md`
- Data contracts: `docs/DATA_CONTRACTS.md`
- Events: `docs/EVENTS.md`
- Stripe Connect local setup: `docs/STRIPE_CONNECT_LOCAL_SETUP.md`
