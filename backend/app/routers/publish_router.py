from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin, require_editor
from ..db import get_db
from ..models import PublishRun, User
from ..schemas import PublishRunOut
from ..services import catalog_read, publish, validation
from ..storage import get_storage

router = APIRouter(prefix="/admin", tags=["admin: publish"])


@router.get("/validation-report")
def validation_report(db: Session = Depends(get_db), _: User = Depends(require_editor)):
    """Editors need to see what's blocking, so this is editor-level, not admin."""
    return validation.report(db)


@router.post("/catalog/publish", response_model=PublishRunOut)
def publish_catalog(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        run = publish.publish(db, get_storage(), user)
    except publish.PublishBlocked as blocked:
        raise HTTPException(409, {"message": blocked.report["summary"],
                                  "report": blocked.report}) from None
    except publish.PublishInProgress as busy:
        raise HTTPException(423, str(busy)) from None
    catalog_read.invalidate()
    return run


@router.post("/catalog/dry-run")
def publish_dry_run(db: Session = Depends(get_db), _: User = Depends(require_editor)):
    """What would change if I pressed Publish? No writes, no run recorded."""
    return {"report": validation.report(db), "diff": publish.diff_against_live(db, get_storage())}


@router.get("/catalog/runs", response_model=list[PublishRunOut])
def runs(db: Session = Depends(get_db), _: User = Depends(require_editor), limit: int = 25):
    publish.sweep_stale_runs(db)
    return db.query(PublishRun).order_by(PublishRun.started_at.desc()).limit(limit).all()


@router.post("/catalog/rollback/{run_id}", response_model=PublishRunOut)
def rollback(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        run = publish.rollback(db, get_storage(), user, run_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    catalog_read.invalidate()
    return run
