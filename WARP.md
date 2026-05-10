# WARP.md

This repository is centered on:
- `java-platform/` — main Spring Boot application
- `app/` — Python FastAPI + LangGraph AI/runtime service

## Common commands

### Java app
```bash
cd java-platform
./mvnw spring-boot:run
./mvnw test -q
```

### Python service
```bash
./run_backend.sh
```

### Infra
```bash
docker compose -f docker-compose-simple.yml up -d
```

## Local URLs
- Java app: `http://127.0.0.1:8080`
- Python docs: `http://127.0.0.1:8000/docs`

## Architecture note
Treat the Java app as the main product surface.
Treat the Python service as the FastAPI + LangGraph AI/runtime support layer.
