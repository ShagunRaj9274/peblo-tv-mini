"""Seeds the database from data/seed_shows.json.

The seed data is deliberately imperfect. The seeder's job is *not* to silently
clean it: an import that quietly fixes bad data hides the problem from the people
who own the content. So the rule here is:

  * Anything that is a formatting difference (a "11:20" duration, a
    "14-04-2025" date, padded whitespace) is normalised and noted.
  * Anything that is a content decision (an unknown category, a duplicate
    language variant, a missing section) is imported *as-is* and left for the
    validation report to surface to an editor. It just can't be published.
  * Anything the database will not physically accept (a duplicate
    content_group + language, a negative duration) is imported with the offending
    field neutralised, and recorded in the import log.

The import log is printed on startup and written to the audit log.
"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .auth import hash_password
from .config import settings
from .models import Artwork, AuditLog, Episode, Season, Show, User
from .reference import languages as allowed_languages
from .services import artwork as art_service
from .storage import get_storage

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y")


def _duration(raw) -> tuple[int | None, str | None]:
    if raw is None or raw == "":
        return None, "no duration given"
    if isinstance(raw, int):
        return (raw, None) if raw > 0 else (None, f"duration was {raw}, which isn't a real runtime")
    if isinstance(raw, str) and ":" in raw:
        try:
            parts = [int(p) for p in raw.split(":")]
            if len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
            else:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            return seconds, f"duration '{raw}' read as {seconds} seconds"
        except ValueError:
            return None, f"couldn't read the duration '{raw}'"
    try:
        n = int(raw)
        return (n, None) if n > 0 else (None, f"duration was {raw}")
    except (TypeError, ValueError):
        return None, f"couldn't read the duration '{raw}'"


def _date(raw):
    if not raw:
        return None, None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date(), (
                None if fmt == "%Y-%m-%d" else f"release date '{raw}' read as {fmt}")
        except ValueError:
            continue
    return None, f"couldn't read the release date '{raw}'"


def _status(raw: str) -> tuple[str, str | None]:
    value = (raw or "draft").strip().lower()
    if value in ("draft", "published", "archived"):
        return value, None
    return "draft", f"status '{raw}' isn't one we know, imported as draft"


def seed_users(db: Session) -> None:
    wanted = [
        (settings.seed_admin_email, "Asha Menon", settings.seed_admin_password, "admin"),
        (settings.seed_editor_email, "Ravi Kulkarni", settings.seed_editor_password, "editor"),
    ]
    for email, name, password, role in wanted:
        if not db.query(User).filter(User.email == email).count():
            db.add(User(email=email, name=name, password_hash=hash_password(password), role=role))
    db.commit()


def _attach_demo_artwork(db: Session, shows: dict[str, Show], episodes: list[Episode]) -> int:
    """Uploads the sample assets through the same validation path the CMS uses,
    so the seeded catalogue is publishable out of the box."""
    assets = Path(settings.seed_assets_dir)
    storage = get_storage()
    pairs = {"poster": assets / "poster_good.jpg", "banner": assets / "banner_good.jpg"}
    thumb_path = assets / "thumb_good.jpg"
    if not thumb_path.exists():
        return 0

    count = 0
    cache: dict[str, art_service.InspectedImage] = {}
    for kind, path in pairs.items():
        if not path.exists():
            continue
        cache[kind] = art_service.inspect(path.read_bytes())
        art_service.validate(kind, cache[kind])
    cache["thumbnail"] = art_service.inspect(thumb_path.read_bytes())
    art_service.validate("thumbnail", cache["thumbnail"])

    for show in shows.values():
        for kind in ("poster", "banner"):
            if kind not in cache:
                continue
            image = cache[kind]
            key = art_service.storage_key("show", show.id, kind, image)
            storage.put(key, image.data, image.mime)
            db.add(Artwork(owner_type="show", owner_id=show.id, kind=kind, storage_key=key,
                           mime_type=image.mime, width=image.width, height=image.height,
                           bytes=image.bytes, checksum=image.checksum))
            count += 1

    image = cache["thumbnail"]
    for ep in episodes:
        key = art_service.storage_key("episode", ep.id, "thumbnail", image)
        storage.put(key, image.data, image.mime)
        db.add(Artwork(owner_type="episode", owner_id=ep.id, kind="thumbnail", storage_key=key,
                       mime_type=image.mime, width=image.width, height=image.height,
                       bytes=image.bytes, checksum=image.checksum))
        count += 1
    db.commit()
    return count


def seed_content(db: Session, *, with_artwork: bool = True) -> dict:
    if db.query(Show).count():
        return {"skipped": "content already present"}

    rows = json.loads(Path(settings.seed_path).read_text())
    log: list[str] = []
    shows: dict[str, Show] = {}
    seasons: dict[tuple[str, int], Season] = {}
    episodes: list[Episode] = []
    taken_group_lang: set[tuple[str, str]] = set()

    for row in rows:
        slug = (row.get("show_slug") or "").strip()
        if not slug:
            log.append(f"row {row.get('episode_id')}: no show, skipped")
            continue

        show = shows.get(slug)
        if show is None:
            section = (row.get("section") or "").strip() or None
            show = Show(
                slug=slug,
                title=(row.get("show_title") or slug).strip(),
                synopsis=(row.get("show_synopsis") or "").strip(),
                category=(row.get("category") or "").strip() or None,
                section=section,
                # Anything with content problems still imports; it just imports as
                # a draft so it cannot leak into the catalogue by accident.
                status="published" if section else "draft",
                featured=slug in ("kabir-and-the-kite",),
                sort_weight=100,
            )
            if not section:
                log.append(f"{slug}: no section in the seed data, imported as draft")
            db.add(show)
            db.flush()
            shows[slug] = show

        number = int(row.get("season_number") or 0)
        season = seasons.get((slug, number))
        if season is None:
            season = Season(show_id=show.id, season_number=number,
                            title=(row.get("season_title") or "").strip()
                            or ("Trailers" if number == 0 else f"Season {number}"))
            db.add(season)
            db.flush()
            seasons[(slug, number)] = season

        duration, note = _duration(row.get("duration_seconds"))
        if note:
            log.append(f"{slug} · {row.get('title')}: {note}")
        release, dnote = _date(row.get("release_date"))
        if dnote:
            log.append(f"{slug} · {row.get('title')}: {dnote}")
        ep_status, snote = _status(row.get("status"))
        if snote:
            log.append(f"{slug} · {row.get('title')}: {snote}")

        group = (row.get("content_group") or "").strip() or None
        language = (row.get("language") or "en").strip()
        if group and (group, language) in taken_group_lang:
            log.append(
                f"{slug} · {row.get('title')} ({language}): another episode already claims content "
                f"group '{group}' for this language — imported without a content group and left as "
                f"draft for an editor to resolve"
            )
            group = None
            ep_status = "draft"
        if group:
            taken_group_lang.add((group, language))

        if language not in allowed_languages():
            log.append(
                f"{slug} · {row.get('title')}: language '{language}' isn't one we ship — imported "
                f"as draft for an editor to re-tag"
            )
            ep_status = "draft"
        if not group and ep_status == "published":
            log.append(
                f"{slug} · {row.get('title')}: no content group, so its language versions can't be "
                f"linked — imported as draft"
            )
            ep_status = "draft"
        if not duration:
            ep_status = "draft"  # cannot be published without one; the report says why

        episode = Episode(
            season_id=season.id,
            episode_number=int(row.get("episode_number") or 1),
            title=" ".join((row.get("title") or "Untitled").split()),
            synopsis=(row.get("synopsis") or "").strip(),
            duration_seconds=duration,
            language=language,
            content_group=group,
            status=ep_status,
            release_date=release,
            source_ref=row.get("episode_id"),
        )
        db.add(episode)
        db.flush()
        episodes.append(episode)

    db.commit()

    art_count = _attach_demo_artwork(db, shows, episodes) if with_artwork else 0

    db.add(AuditLog(actor_email="system", entity="import", entity_id="seed",
                    action="seed", detail={"rows": len(rows), "notes": log}))
    db.commit()

    return {
        "rows": len(rows),
        "shows": len(shows),
        "seasons": len(seasons),
        "episodes": len(episodes),
        "artwork": art_count,
        "notes": log,
    }


def run(db: Session) -> dict:
    seed_users(db)
    result = seed_content(db)
    return result
