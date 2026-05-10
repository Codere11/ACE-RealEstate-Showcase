#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export ACE_BOOTSTRAP_DB="${ACE_BOOTSTRAP_DB:-0}"
export ACE_PYTHON_BACKEND_URL="${ACE_PYTHON_BACKEND_URL:-http://127.0.0.1:8000}"

if [[ -z "${DATABASE_URL:-}" && -n "${ACE_DB_URL:-}" && -n "${ACE_DB_USERNAME:-}" && -n "${ACE_DB_PASSWORD:-}" ]]; then
  export DATABASE_URL="$(python3 - <<'PY'
import os
from urllib.parse import quote, urlsplit, urlunsplit

jdbc_url = os.environ["ACE_DB_URL"]
if not jdbc_url.startswith("jdbc:postgresql://"):
    raise SystemExit("ACE_DB_URL must start with jdbc:postgresql:// when DATABASE_URL is not set")
parsed = urlsplit(jdbc_url[len("jdbc:"):])
username = quote(os.environ["ACE_DB_USERNAME"], safe="")
password = quote(os.environ["ACE_DB_PASSWORD"], safe="")
netloc = f"{username}:{password}@{parsed.netloc}"
print(urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)))
PY
)"
fi

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
PYTHON_PID=$!

cleanup() {
  kill "$PYTHON_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

exec java -jar /app/java/app.jar
