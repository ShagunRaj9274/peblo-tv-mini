import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import catalog_read, publish
from ..storage import get_storage

router = APIRouter(tags=["ops"])
STARTED = time.time()


@router.get("/health")
def health():
    """Liveness. Deliberately cheap — no dependencies — so a slow database
    doesn't get the container killed by the orchestrator."""
    return {"status": "ok", "uptime_seconds": round(time.time() - STARTED, 1)}


@router.get("/health/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    """Readiness. Checks the things a request actually needs, and reports the
    age of the published catalogue — see README for what we alert on."""
    checks: dict[str, dict] = {}
    ok = True

    try:
        db.execute(text("select 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        ok = False
        checks["database"] = {"ok": False, "error": str(exc)[:200]}

    storage = get_storage()
    try:
        key = publish.current_key(storage)
        published = bool(key and storage.exists(key))
        checks["storage"] = {"ok": True, "catalog_published": published, "catalog_key": key}
        if not published:
            checks["storage"]["note"] = "No catalogue published yet. The viewer will show an empty state."
    except Exception as exc:  # noqa: BLE001
        ok = False
        checks["storage"] = {"ok": False, "error": str(exc)[:200]}

    doc = catalog_read.snapshot(storage)
    checks["catalog"] = {"ok": doc is not None, "counts": (doc or {}).get("counts", {})}

    if not ok:
        response.status_code = 503
    return {"status": "ok" if ok else "degraded", "checks": checks}
