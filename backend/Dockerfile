FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
# Seed content and reference data live outside the backend so the same image can
# be pointed at a different content bundle without a rebuild.
COPY data/ /data/seed/
COPY assets/ /data/assets/

ENV REFERENCE_PATH=/data/seed/reference.json \
    SEED_PATH=/data/seed/seed_shows.json \
    SEED_ASSETS_DIR=/data/assets \
    STORAGE_LOCAL_ROOT=/data/storage

RUN chmod +x /app/entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=25s --retries=6 \
  CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["/app/entrypoint.sh"]
