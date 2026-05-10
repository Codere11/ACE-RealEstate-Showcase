FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /workspace/java-platform

COPY java-platform/.mvn/ .mvn/
COPY java-platform/mvnw java-platform/pom.xml ./
RUN chmod +x mvnw && ./mvnw -q -DskipTests dependency:go-offline

COPY java-platform/src ./src
RUN ./mvnw -q -DskipTests package

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ACE_BOOTSTRAP_DB=0

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    gcc \
    libpq-dev \
    openjdk-21-jre-headless \
    postgresql-client \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY static/ ./static/
COPY docker/unified-entrypoint.sh /app/unified-entrypoint.sh
COPY --from=java-build /workspace/java-platform/target/*.jar /app/java/app.jar

RUN mkdir -p /app/static/avatars /app/static/org_avatars /app/instances /app/java \
    && chmod +x /app/unified-entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD ["sh", "-c", "curl -fsS http://127.0.0.1:${PORT:-8080}/actuator/health >/dev/null || exit 1"]

ENTRYPOINT ["/app/unified-entrypoint.sh"]
