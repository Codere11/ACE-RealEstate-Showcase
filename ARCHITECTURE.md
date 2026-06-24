# Architecture — ACE

See **[CONTEXT.md](CONTEXT.md)** for full data model, API, and AI flow.

## High-level

```
Visitor Browser → FastAPI :8000 → PostgreSQL :5433
                                  → LiveKit :7880
```

## Stack

| Layer | Tech |
|---|---|
| Backend | Python FastAPI |
| AI | LangGraph + OpenAI/DeepSeek |
| Frontend | Angular 19 SPA |
| DB | PostgreSQL 15 |
| Video | LiveKit |

Single Python process. No Java. Angular SPA served as static files.

## Directories

```
backend/          Server — routes, auth, events, LiveKit tokens, models
app/              AI library — LangGraph graph, B2B tools, LLM client
angular-visitor/  Frontend — chat widget, video overlay, staff dashboard
scripts/          B2B simulator, demo seed data
docs/             Specs
```
