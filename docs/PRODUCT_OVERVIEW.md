# Product Overview

ACE Reception Services is an AI receptionist platform for Slovenian beauty salons (kozmeticni saloni). It replaces the front-desk experience online.

## North Star

> Make ACE a **no-brainer** for Slovenian beauty salons and similar appointment-based service businesses.

## Why salons

Beauty salons already have the perfect business model to digitalize:
- Someone walks in → talks with the receptionist → asks questions → selects a service → gets it done
- Higher transaction volume than real-estate → faster revenue via commissions
- Instantly relatable to salon owners — they live this flow every day

## Product thesis

> Let visitors feel like they're walking into a real salon with a real receptionist — just digital.

## Main product layers

### 1. AI Receptionist (Visitor Side — Angular SPA)
The core product surface. An inviting AI receptionist sits middle-bottom of the page:
- Greets visitors naturally in Slovenian
- Answers questions about services, pricing, and availability
- Navigates visitors to relevant sections of the page
- Helps select and book services via calendar
- Shows open/closed hours with live status
- Hands off to human staff with a premium slow fade-in

### 2. Live Staff Handoff
Visitors have full control over human interaction:
- **Accept/Deny** when staff wants to join — some visitors don't want it
- **Request a human** — visitor can explicitly ask for staff
- **Slow fade-in** of staff camera — feels like "streaming tokens," not a jarring pop-in

### 3. Manager Dashboard (Java + Thymeleaf)
Salon staff manage everything from one place:
- Calendar and appointment management
- Lead and conversation overview
- Join/leave visitor conversations
- Live video handoff initiation
- Service and operating hours management
- Open/closed status control

### 4. AI Brain (Python + LangGraph)
The Python service powers the receptionist:
- Intent routing: greet → qualify → inform → book → handoff
- Conversational behavior tailored to salon context
- Open/closed hours awareness — different behavior when staff is unavailable

## Current demo concept
- 3 demo beauty services with AI-generated photos
- AI receptionist chat
- Open/closed status awareness
- Calendar + appointment booking
- Live staff video handoff with fade-in

## Implementation shape
- **Angular** — visitor-side SPA
- **Java Spring Boot + Thymeleaf** — backend API + dashboard
- **Python FastAPI + LangGraph** — AI/runtime service
- **PostgreSQL** — persistence
- **LiveKit** — live staff video handoff

## Where to read next
- `Reception-Services.txt` — project goal and north star
- `ARCHITECTURE.md`
- `docs/LOCAL_DEVELOPMENT.md`
- `docs/API_OVERVIEW.md`
