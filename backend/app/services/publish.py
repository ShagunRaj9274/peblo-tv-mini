"""The publish job.

Atomicity, concretely:
  1. Build the document in memory and checksum it.
  2. Write it to an *immutable, run-scoped key*: catalog/runs/<run_id>.json.
     Nothing reads this key yet, so a partial or failed write is invisible.
  3. Flip one small pointer object (catalog/current.pointer) to that key.
     Local disk: fsync + os.replace, atomic on POSIX. R2: a single PUT.

A reader resolves the pointer, then fetches the immutable key. It therefore sees
either the whole previous catalogue or the whole new one — never a half-written
file, and never a file that changes under it mid-read.

If the process dies: any run left in `running` is swept to `failed` on the next
startup (and by an advisory-lock guard on the next publish). The pointer was
never touched, so the live catalogue is still the last good one. The orphaned
run file is garbage, kept for debugging and cleaned by retention.
"""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import PublishRun, User
from ..storage import ObjectStorage
from . import catalog_build, validation

POINTER = "catalog/current"
RUN_KEY = "catalog/runs/{run_id}.json"
STALE_AFTER = timedelta(minutes=15)


class PublishBlocked(Exception):
    def __init__(self, report: dict):
        self.report = report
        super().__init__(report["summary"])


class PublishInProgress(Exception):
    pass


def sweep_stale_runs(db: Session) -> int:
    """A run still marked `running` after STALE_AFTER means the process died.
    The live pointer is untouched, so this is bookkeeping, not recovery."""
    cutoff = datetime.now(UTC) - STALE_AFTER
    stale = db.query(PublishRun).filter(PublishRun.status == "running").all()
    n = 0
    for run in stale:
        started = run.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if started < cutoff:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error = "Publish process stopped before finishing. The live catalogue was not changed."
            n += 1
    if n:
        db.commit()
    return n


def _take_lock(db: Session) -> bool:
    """One publish at a time, cluster-wide. Postgres advisory lock; on sqlite
    (tests) we fall back to the run table."""
    if db.bind.dialect.name == "postgresql":
        return bool(db.execute(text("select pg_try_advisory_lock(823411)")).scalar())
    return not db.query(PublishRun).filter(PublishRun.status == "running").count()


def _release_lock(db: Session) -> None:
    if db.bind.dialect.name == "postgresql":
        db.execute(text("select pg_advisory_unlock(823411)"))
        db.commit()


def current_key(storage: ObjectStorage) -> str | None:
    return storage.get_pointer(POINTER)


def load_current(storage: ObjectStorage) -> dict | None:
    key = current_key(storage)
    if not key or not storage.exists(key):
        return None
    return json.loads(storage.get(key))


def diff_against_live(db: Session, storage: ObjectStorage) -> dict:
    """Dry run: what would change if I pressed Publish right now?"""
    candidate = catalog_build.build(db, storage)
    live = load_current(storage) or {"shows": []}
    live_by_slug = {s["slug"]: s for s in live.get("shows", [])}
    new_by_slug = {s["slug"]: s for s in candidate["shows"]}

    def fingerprint(show: dict) -> str:
        return catalog_build.checksum(show)

    added = sorted(set(new_by_slug) - set(live_by_slug))
    removed = sorted(set(live_by_slug) - set(new_by_slug))
    changed = sorted(
        slug for slug in set(new_by_slug) & set(live_by_slug)
        if fingerprint(new_by_slug[slug]) != fingerprint(live_by_slug[slug])
    )
    return {
        "added": [{"slug": s, "title": new_by_slug[s]["title"]} for s in added],
        "removed": [{"slug": s, "title": live_by_slug[s]["title"]} for s in removed],
        "changed": [{"slug": s, "title": new_by_slug[s]["title"]} for s in changed],
        "counts": candidate["counts"],
        "live_counts": live.get("counts", {}),
        "would_change": bool(added or removed or changed),
    }


def publish(db: Session, storage: ObjectStorage, actor: User, force: bool = False) -> PublishRun:
    sweep_stale_runs(db)
    report = validation.report(db)

    if not report["can_publish"] and not force:
        run = PublishRun(
            actor_id=actor.id, actor_email=actor.email, status="blocked",
            finished_at=datetime.now(UTC),
            counts={"blocking": report["blocking_count"], "warnings": report["warning_count"]},
            error=report["summary"],
        )
        db.add(run)
        db.commit()
        raise PublishBlocked(report)

    if not _take_lock(db):
        raise PublishInProgress("Another publish is already running. Wait for it to finish.")

    run = PublishRun(actor_id=actor.id, actor_email=actor.email, status="running", counts={})
    db.add(run)
    db.commit()

    try:
        document = catalog_build.build(db, storage)
        digest = catalog_build.checksum(document)

        previous = (
            db.query(PublishRun)
            .filter(PublishRun.status.in_(["success", "no_changes"]))
            .order_by(PublishRun.started_at.desc())
            .first()
        )
        live_key = current_key(storage)

        # Idempotent: identical content, identical bytes -> don't churn the pointer,
        # don't invalidate caches, but still record that someone pressed the button.
        if previous and previous.checksum == digest and live_key and storage.exists(live_key):
            run.status = "no_changes"
            run.catalog_key = live_key
            run.checksum = digest
            run.counts = {**document["counts"], "warnings": report["warning_count"]}
            run.finished_at = datetime.now(UTC)
            db.commit()
            return run

        key = RUN_KEY.format(run_id=run.id)
        payload = json.dumps(
            catalog_build.stamp(document, run.id), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

        storage.put(key, payload, "application/json")   # (2) immutable write, nobody reads it yet
        storage.set_pointer(POINTER, key)                # (3) the single atomic swap

        run.status = "success"
        run.catalog_key = key
        run.checksum = digest
        run.counts = {**document["counts"], "warnings": report["warning_count"],
                      "bytes": len(payload)}
        run.finished_at = datetime.now(UTC)
        db.commit()
        return run
    except Exception as exc:  # noqa: BLE001 - the run row is the operator's breadcrumb
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.now(UTC)
        db.commit()
        raise
    finally:
        _release_lock(db)


def rollback(db: Session, storage: ObjectStorage, actor: User, target_run_id: str) -> PublishRun:
    """Stretch goal. Rollback is the same atomic operation as publish: point at an
    older immutable file. No rebuild, so it is fast and cannot fail halfway."""
    target = db.get(PublishRun, target_run_id)
    if not target or not target.catalog_key or not storage.exists(target.catalog_key):
        raise ValueError("That run has no catalogue file to roll back to.")
    run = PublishRun(
        actor_id=actor.id, actor_email=actor.email, status="running",
        counts={"rolled_back_to": target_run_id},
    )
    db.add(run)
    db.commit()
    storage.set_pointer(POINTER, target.catalog_key)
    run.status = "success"
    run.catalog_key = target.catalog_key
    run.checksum = target.checksum
    run.counts = {**(target.counts or {}), "rolled_back_to": target_run_id}
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run
