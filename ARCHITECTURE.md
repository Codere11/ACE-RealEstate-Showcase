<!-- Created: 2026-03-14T20:44:39Z -->
# Architecture — ACE Real Estate

System overview
```mermaid
graph TD
    User[User] -->|Survey| SurveyPage[Survey Page (Angular)]
    SurveyPage --> API[FastAPI Backend]
    API --> DB[(PostgreSQL)]
    API --> LeadScoring[Lead Scoring Service]
    LeadScoring --> OperatorDash[Operator Dashboard]
    OperatorDash --> API
```

Lead qualification flow
```mermaid
sequenceDiagram
    participant U as User
    participant FE as Survey Page (Angular)
    participant BE as FastAPI API
    participant LS as Lead Scoring
    participant DB as PostgreSQL
    participant OD as Operator Dashboard

    U->>FE: Submit survey
    FE->>BE: POST /leads (payload)
    BE->>DB: Insert lead (status=pending)
    BE->>LS: Score lead (async/sync)
    LS-->>BE: score=0..100, qualifiers
    BE->>DB: Update lead (score, status)
    BE-->>FE: 200 Created + lead_id
    BE-->>OD: WebSocket/event: "high-score lead"
    OD->>BE: Operator engage (takeover)
```

Key technical points
- Multi-tenant isolation with per-tenant flows and assets
- Node-based conversation engine with AI-assisted scoring
- Event-driven operator handoff to dashboard (WebSocket/events)
- Dockerized local stack (Postgres + FastAPI + UIs)
