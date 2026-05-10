# ACE e-Counter

ACE e-Counter is now primarily a **Java Spring Boot application** with a **Python AI/runtime service**.

This repo still contains legacy Angular and older Python-first pieces, but the current product truth is:

- `java-platform/` is the main app users see
- `app/` is the Python AI/runtime service and some legacy APIs
- legacy Angular frontends remain in the repo as transitional/reference code, not as the main product surface

## Current truth

### Main product surface
The main product now lives in **Spring Boot + Thymeleaf** inside `java-platform/`.

It currently owns most of the user-visible product:
- login and auth
- organization dashboard
- lead thread / takeover UI
- surveys and qualifier management UI
- live-help preview / go-live controls
- payment request flow
- public visitor pages

### Python service role
The Python app in `app/` still matters, but its role is narrower now.

It is mainly used for:
- AI/runtime logic
- event and runtime support paths
- some legacy APIs that have not been moved yet
- transitional support for features still bridged from Java

## Architecture summary

### What owns what now
- **Java (`java-platform/`)**: main web app, dashboard, public site, auth, surveys, current payment flow, current live-session UI flow
- **Python (`app/`)**: AI qualifier/runtime behavior, supporting runtime services, some legacy endpoints
- **PostgreSQL**: shared persistence
- **LiveKit**: local live-help transport during demo/testing
- **Stripe**: payment requests and Connect/onboarding path

### What this project demonstrates
- multi-tenant product design
- Java app migration/re-platforming work
- Python AI runtime integration instead of hard-coding AI into the main app
- manager-side operations + visitor-side flow in one product
- live help + payment request + qualification in one system

## Current demoable story
1. visitor opens the Java public experience
2. survey or open qualification flow starts
3. manager opens the Java dashboard
4. manager inspects lead thread and qualifier output
5. manager can take over chat or go live
6. manager can send a payment request
7. visitor receives a clean payment button and opens hosted checkout

## Repo status
This repo is in a **transition state**, but the direction is clear.

### Primary code now
- `java-platform/` → primary application
- `app/` → AI/runtime service used by the Java app

### Legacy / transitional code still present
- `frontend/ACE-Chatbot/` → legacy Angular visitor UI
- `frontend/manager-dashboard/` → legacy Angular manager dashboard
- `portal/portal/` → older admin UI
- `docker-compose-simple.yml` → still reflects the older Angular/Python-first local stack

These are not the main truth anymore.
They remain because cleanup/splitting is still in progress.

## Recommended local development path
If you want to work on the current product shape, use the **Java-first** path.

### 1. Start infra
```bash
docker compose -f docker-compose-simple.yml up -d postgres livekit
```

### 2. Create the Java app database once
The legacy compose file creates `ace_production`, but the Java app expects `ace_platform` by default.

```bash
docker exec -it ace-postgres psql -U ace_user -c "CREATE DATABASE ace_platform;"
```

### 3. Run the Java app
```bash
cd java-platform
./mvnw spring-boot:run
```

### 4. Optionally run the Python AI/runtime service
```bash
cd /home/maksich/Documents/ACE-RealEstate
./run_backend.sh
```

### Main local URLs
- Java app: `http://127.0.0.1:8080`
- Demo org dashboard: `http://127.0.0.1:8080/demo/dashboard`
- Login: `http://127.0.0.1:8080/login`
- Demo credentials: `admin / test123`
- Python service docs: `http://127.0.0.1:8000/docs`

## Documentation
- Current architecture: `ARCHITECTURE.md`
- Current local dev path: `docs/LOCAL_DEVELOPMENT.md`
- Product overview: `docs/PRODUCT_OVERVIEW.md`
- API overview: `docs/API_OVERVIEW.md`

## Repository map
- `java-platform/` — primary Spring Boot application
- `app/` — Python AI/runtime service
- `docs/` — documentation
- `scripts/` — seed/helper scripts
- `frontend/ACE-Chatbot/` — legacy Angular visitor app
- `frontend/manager-dashboard/` — legacy Angular manager dashboard
- `portal/portal/` — legacy/older admin UI

## Notes
- The repo still needs structural cleanup
- The docs now describe the current truth, not the old marketing story
- Next cleanup step should be moving legacy Angular/old-stack code into clearly marked legacy boundaries or a separate repo

## Author
Maks Ponikvar

## Contact
- Email: `maks.ponikvar@gmail.com`
- GitHub: `https://github.com/Codere11`
