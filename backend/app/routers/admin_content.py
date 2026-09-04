import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import require_editor
from ..db import get_db
from ..models import Artwork, AuditLog, Episode, Season, Show, User
from ..reference import categories, languages, sections
from ..schemas import (
    EpisodeIn,
    EpisodeOut,
    EpisodeUpdate,
    Page,
    SeasonIn,
    SeasonOut,
    ShowIn,
    ShowOut,
    ShowUpdate,
)
from ..storage import get_storage

router = APIRouter(prefix="/admin", tags=["admin: content"])


def _audit(db: Session, actor: User, entity: str, entity_id: str, action: str, detail: dict | None = None):
    db.add(AuditLog(actor_email=actor.email, entity=entity, entity_id=entity_id,
                    action=action, detail=detail or {}))


def _artwork_for(db: Session, owner_type: str, owner_ids: list[str]) -> dict[str, list[dict]]:
    if not owner_ids:
        return {}
    storage = get_storage()
    out: dict[str, list[dict]] = {}
    rows = db.query(Artwork).filter(Artwork.owner_type == owner_type,
                                    Artwork.owner_id.in_(owner_ids)).all()
    for a in rows:
        out.setdefault(a.owner_id, []).append({
            "id": a.id, "kind": a.kind, "width": a.width, "height": a.height,
            "bytes": a.bytes, "mime_type": a.mime_type, "url": storage.public_url(a.storage_key),
        })
    return out


def _show_payload(db: Session, show: Show) -> dict:
    eps = [e for s in show.seasons for e in s.episodes]
    return {
        **{c: getattr(show, c) for c in
           ("id", "slug", "title", "synopsis", "category", "section", "status", "featured",
            "sort_weight", "updated_at")},
        "synopsis": show.synopsis or "",
        "seasons": [SeasonOut.model_validate(s).model_dump() for s in show.seasons],
        "artwork": _artwork_for(db, "show", [show.id]).get(show.id, []),
        "episode_count": len(eps),
        "languages": sorted({e.language for e in eps}),
    }


@router.get("/reference")
def get_reference(_: User = Depends(require_editor)):
    """The CMS builds its dropdowns from this, so the two can't drift."""
    from ..reference import artwork_specs

    return {"sections": sections(), "categories": categories(), "languages": languages(),
            "artwork": artwork_specs()}


@router.get("/shows", response_model=Page)
def list_shows(
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
    q: str | None = None,
    section: str | None = None,
    show_status: str | None = Query(None, alias="status"),
    language: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = db.query(Show).options(selectinload(Show.seasons).selectinload(Season.episodes))
    if q:
        like = f"%{q.lower()}%"
        matching = (
            db.query(Season.show_id)
            .join(Episode, Episode.season_id == Season.id)
            .filter(func.lower(Episode.title).like(like))
            .subquery()
        )
        query = query.filter(
            or_(func.lower(Show.title).like(like), func.lower(Show.slug).like(like),
                func.lower(func.coalesce(Show.category, "")).like(like), Show.id.in_(matching))
        )
    if section:
        query = query.filter(Show.section == section)
    if show_status:
        query = query.filter(Show.status == show_status)
    if language:
        with_lang = (
            db.query(Season.show_id)
            .join(Episode, Episode.season_id == Season.id)
            .filter(Episode.language == language)
            .subquery()
        )
        query = query.filter(Show.id.in_(with_lang))

    total = query.order_by(None).count()
    rows = query.order_by(Show.title).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_show_payload(db, s) for s in rows],
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)),
    }


@router.post("/shows", response_model=ShowOut, status_code=201)
def create_show(payload: ShowIn, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    if db.query(Show).filter(Show.slug == payload.slug).count():
        raise HTTPException(409, f"A show already uses the URL slug “{payload.slug}”. Pick another.")
    if payload.status == "published" and not payload.section:
        raise HTTPException(422, "A published show needs a section, or it has no row to appear in.")
    show = Show(**payload.model_dump())
    db.add(show)
    db.flush()
    db.add(Season(show_id=show.id, season_number=0, title="Trailers"))
    db.add(Season(show_id=show.id, season_number=1, title="Season 1"))
    _audit(db, user, "show", show.id, "create", {"title": show.title})
    db.commit()
    db.refresh(show)
    return _show_payload(db, show)


@router.get("/shows/{show_id}", response_model=ShowOut)
def get_show(show_id: str, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(404, "We couldn't find that show. It may have been deleted.")
    return _show_payload(db, show)


@router.patch("/shows/{show_id}", response_model=ShowOut)
def update_show(show_id: str, payload: ShowUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_editor)):
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(404, "We couldn't find that show. It may have been deleted.")
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status", show.status)
    new_section = data.get("section", show.section)
    if new_status == "published" and not new_section:
        raise HTTPException(422, "A published show needs a section, or it has no row to appear in.")
    for k, v in data.items():
        setattr(show, k, v)
    _audit(db, user, "show", show.id, "update", data)
    db.commit()
    db.refresh(show)
    return _show_payload(db, show)


@router.delete("/shows/{show_id}", status_code=204)
def delete_show(show_id: str, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(404, "We couldn't find that show. It may have been deleted.")
    _audit(db, user, "show", show.id, "delete", {"title": show.title})
    db.delete(show)
    db.commit()


@router.post("/shows/{show_id}/seasons", response_model=SeasonOut, status_code=201)
def create_season(show_id: str, payload: SeasonIn, db: Session = Depends(get_db),
                  user: User = Depends(require_editor)):
    if not db.get(Show, show_id):
        raise HTTPException(404, "We couldn't find that show.")
    season = Season(show_id=show_id, **payload.model_dump())
    db.add(season)
    try:
        _audit(db, user, "season", season.id, "create", payload.model_dump())
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"This show already has a season {payload.season_number}.") from None
    db.refresh(season)
    return season


@router.get("/shows/{show_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(show_id: str, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    season_ids = [s.id for s in db.query(Season).filter(Season.show_id == show_id).all()]
    eps = (
        db.query(Episode).filter(Episode.season_id.in_(season_ids))
        .order_by(Episode.episode_number, Episode.language).all()
    )
    art = _artwork_for(db, "episode", [e.id for e in eps])
    return [
        {**{c: getattr(e, c) for c in
            ("id", "season_id", "episode_number", "title", "synopsis", "duration_seconds",
             "language", "content_group", "status", "release_date")},
         "synopsis": e.synopsis or "", "artwork": art.get(e.id, [])}
        for e in eps
    ]


def _episode_guard(db: Session, episode: Episode, data: dict) -> None:
    """The publish-blocking rules, enforced at write time so an editor finds out
    now rather than on the publish screen."""
    status_after = data.get("status", episode.status if episode else "draft")
    if status_after != "published":
        return
    duration = data.get("duration_seconds", episode.duration_seconds if episode else None)
    if not duration:
        raise HTTPException(422, "This episode needs a runtime before it can be published.")
    if episode:
        has_thumb = db.query(Artwork).filter(
            Artwork.owner_type == "episode", Artwork.owner_id == episode.id,
            Artwork.kind == "thumbnail").count()
        if not has_thumb:
            raise HTTPException(422, "Upload a 640×360 thumbnail before publishing this episode.")


@router.post("/episodes", response_model=EpisodeOut, status_code=201)
def create_episode(payload: EpisodeIn, db: Session = Depends(get_db),
                   user: User = Depends(require_editor)):
    if not db.get(Season, payload.season_id):
        raise HTTPException(404, "We couldn't find that season.")
    data = payload.model_dump()
    _episode_guard(db, None, data)
    episode = Episode(**data)
    db.add(episode)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            f"There's already a {payload.language} version of “{payload.content_group}”. "
            "Each content group can only have one episode per language.",
        ) from None
    _audit(db, user, "episode", episode.id, "create", {"title": episode.title})
    db.commit()
    db.refresh(episode)
    return {**{c: getattr(episode, c) for c in
               ("id", "season_id", "episode_number", "title", "synopsis", "duration_seconds",
                "language", "content_group", "status", "release_date")},
            "synopsis": episode.synopsis or "", "artwork": []}


@router.patch("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(episode_id: str, payload: EpisodeUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_editor)):
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "We couldn't find that episode.")
    data = payload.model_dump(exclude_unset=True)
    _episode_guard(db, episode, data)
    for k, v in data.items():
        setattr(episode, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Another episode is already the "
            f"{data.get('language', episode.language)} version of that content group.",
        ) from None
    _audit(db, user, "episode", episode.id, "update", data)
    db.commit()
    db.refresh(episode)
    art = _artwork_for(db, "episode", [episode.id]).get(episode.id, [])
    return {**{c: getattr(episode, c) for c in
               ("id", "season_id", "episode_number", "title", "synopsis", "duration_seconds",
                "language", "content_group", "status", "release_date")},
            "synopsis": episode.synopsis or "", "artwork": art}


@router.delete("/episodes/{episode_id}", status_code=204)
def delete_episode(episode_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_editor)):
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "We couldn't find that episode.")
    _audit(db, user, "episode", episode.id, "delete", {"title": episode.title})
    db.delete(episode)
    db.commit()


@router.get("/audit-log")
def audit_log(db: Session = Depends(get_db), _: User = Depends(require_editor), limit: int = 100):
    rows = db.query(AuditLog).order_by(AuditLog.at.desc()).limit(limit).all()
    return [{"at": r.at, "actor": r.actor_email, "entity": r.entity, "entity_id": r.entity_id,
             "action": r.action, "detail": r.detail} for r in rows]


status_codes = status  # re-export for tests
