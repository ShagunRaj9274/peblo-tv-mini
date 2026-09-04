#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for the database…"
python - <<'PY'
import os, time
import psycopg
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
for attempt in range(60):
    try:
        psycopg.connect(url, connect_timeout=2).close()
        print("Database is up.")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Database never became available.")
PY

# Alembic owns the schema. `create_all` in the app is only a safety net for tests.
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
