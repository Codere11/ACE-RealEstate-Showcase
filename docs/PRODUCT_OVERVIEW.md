# Product Overview

## What ACE e-Counter is now
ACE e-Counter is a multi-tenant inbound lead handling product with:
- visitor-facing intake pages
- manager dashboard operations
- AI-assisted qualification
- live human handoff
- payment request flow

Current implementation truth:
- the main app is **Java Spring Boot**
- the AI/runtime side is **Python FastAPI**

This repo still contains legacy Angular/front-end-first code, but that is no longer the best description of the product.

---

## Core product problem
Teams handling inbound leads often suffer from:
- slow manual qualification
- weak context from forms
- disconnected follow-up tools
- poor visibility into who is actually worth pursuing

That creates two failures:
1. visitor experience is clumsy
2. manager decision-making is weak

---

## Product thesis
The product thesis is still simple:

> Let visitors engage naturally, qualify them in the background, give managers decision-quality visibility, and make the next business step actionable.

---

## 1. Visitor intake layer
### What it is now
The visitor-facing experience is currently delivered from the **Java app**.

### What it does
Depending on organization state, the visitor can:
- start in survey mode
- start in open qualification chat mode
- receive live human help
- receive a payment request button in chat

### Why it matters
The product keeps the visitor flow simple while still collecting structured business signal.

---

## 2. AI qualification layer
### What it is now
The AI/runtime layer is primarily in the **Python service**.

### What it does
It supports:
- qualification behavior
- lead profile updates
- reasoning/confidence signals
- next-step logic used by the product

### Why it matters
The Java app owns the main product shell, but AI/runtime logic still belongs in the Python service where iteration is faster and the logic is easier to evolve.

---

## 3. Manager operations layer
### What it is now
The manager dashboard is currently a **Java dashboard**, not the old Angular dashboard.

### What it does
Managers can:
- inspect leads
- read chat threads
- take over conversation
- manage surveys and qualifier config
- preview/go-live for live help
- send payment requests

### Why it matters
This is what turns ACE e-Counter from a chat demo into an operational product.

---

## 4. Conversion layer
### What it is now
Managers can send payment requests from the Java dashboard.
Visitors receive a clean payment button in chat and open hosted checkout.

### Why it matters
The system does not stop at “interesting conversation.”
It drives toward a real business action.

---

## Current coherent demo story
Today the clearest demo story is:
1. visitor opens Java public route
2. survey/chat qualification begins
3. manager opens Java dashboard
4. manager reviews lead and thread
5. manager can take over or go live
6. manager sends payment request
7. visitor opens hosted checkout
8. system reflects payment state back into the flow

---

## What is intentionally unfinished
Still not claimed as finished:
- production-grade live-help polish
- fully hardened deployment setup
- full cleanup of legacy Angular / older Python-first surfaces
- deeper analytics/reporting

That is intentional.
The goal is to anchor the project to the real state it is in.

---

## Where to read next
- Current architecture: `ARCHITECTURE.md`
- Local setup: `docs/LOCAL_DEVELOPMENT.md`
- API overview: `docs/API_OVERVIEW.md`
