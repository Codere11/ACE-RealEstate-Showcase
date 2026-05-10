# Product Overview

ACE e-Counter is a multi-tenant visitor-intake, qualification, and conversion platform.

## Live deployment
- Public app: `https://ace-realestate-showcase-production.up.railway.app/`
- Demo organization: `https://ace-realestate-showcase-production.up.railway.app/demo`

It combines:
- a visitor-facing experience
- a manager dashboard
- AI-assisted qualification
- live human handoff
- payment request flow

## Product thesis

> Let visitors engage naturally, qualify them in the background, give managers clear operational visibility, and make the next business step actionable.

## Main product layers

### 1. Visitor intake
Visitors can start in survey mode or open chat, depending on the organization setup.
The experience stays simple while still collecting useful business signal.

### 2. AI qualification
The Python AI/runtime service uses FastAPI and LangGraph to support qualification behavior, lead-profile updates, and next-step logic.
Managers get more than “the bot had a chat” — they get structure, reasoning, and actionable context.

### 3. Manager operations
The Java dashboard gives managers the tools to act:
- inspect leads
- read chat threads
- take over chat
- manage surveys and qualifier behavior
- preview/go-live for live help
- send payment requests

### 4. Conversion
Managers can send payment requests directly into the visitor chat.
Visitors receive a clean payment button and open hosted checkout.

## Current product story
A strong demo of ACE e-Counter looks like this:
1. visitor opens the public experience
2. survey or open qualification begins
3. manager opens the dashboard
4. manager reviews the lead thread and context
5. manager takes over, goes live, or sends a payment request
6. visitor completes the next step

## Current implementation shape
- **Java Spring Boot** — main application
- **Python FastAPI + LangGraph** — AI/runtime service
- **PostgreSQL** — persistence
- **LiveKit** — live-help transport for demo/testing
- **Stripe** — hosted payment flow

## Current live hosting shape
The current public Railway deployment packages the Java app and Python runtime into one container built from the repo-root `Dockerfile`, with PostgreSQL kept as a separate managed service. This keeps the source split clear while making the live demo simpler and more robust to operate.

## Where to read next
- `ARCHITECTURE.md`
- `docs/LOCAL_DEVELOPMENT.md`
- `docs/API_OVERVIEW.md`
