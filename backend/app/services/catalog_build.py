"""Builds the published catalogue document.

Two hard rules from the brief live here:
  * Season 0 is trailers. It never appears as a season in the viewer.
  * Episodes sharing a content_group are language variants of one episode and
    collapse into a single entry carrying a `languages` list.

The output is deterministic: same database state -> byte-identical JSON. That is
what makes the publish job idempotent (we checksum the document and skip the
pointer flip when nothing changed).
"""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from ..models import Artwork, Episode, Season, Show
from ..reference import TRAILER_SEASON, section_order
from ..storage import ObjectStorage

SCHEMA_VERSION = 1
LANGUAGE_NAMES = {
    "en": "English", "hi": "हिन्दी", "ta": "தமிழ்", "te": "తెలుగు", "bn": "বাংলা", "mr": "मराठी",
}


def _artwork_map(db: Session, storage: ObjectStorage) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = defaultdict(dict)
    for a in db.query(Artwork).all():
        out[(a.owner_type, a.owner_id)][a.kind] = {
            "url": storage.public_url(a.storage_key),
            "width": a.width,
            "height": a.height,
        }
    return out


def _language_entry(code: str) -> dict:
    return {"code": code, "label": LANGUAGE_NAMES.get(code, code.upper())}


def _group_episodes(episodes: list[Episode], art: dict) -> list[dict]:
    """Collapse language variants. Canonical row is English when present,
    otherwise the alphabetically first language — chosen deterministically so
    the catalogue doesn't churn between builds."""
    buckets: dict[str, list[Episode]] = defaultdict(list)
    for ep in episodes:
        # An episode with no content_group is its own group, keyed by id, so it
        # still ships rather than silently vanishing.
        buckets[ep.content_group or f"__ungrouped__{ep.id}"].append(ep)

    entries = []
    for group, variants in buckets.items():
        variants.sort(key=lambda e: (e.language != "en", e.language, e.id))
        canonical = variants[0]
        thumb = art.get(("episode", canonical.id), {}).get("thumbnail")
        # Fall back to any variant's thumbnail rather than rendering a hole.
        if not thumb:
            for v in variants:
                thumb = art.get(("episode", v.id), {}).get("thumbnail")
                if thumb:
                    break
        by_language = sorted(variants, key=lambda e: (e.language != "en", e.language))
        entries.append({
            "content_group": group,
            "episode_number": canonical.episode_number,
            "title": (canonical.title or "").strip(),
            "synopsis": (canonical.synopsis or "").strip(),
            "duration_seconds": canonical.duration_seconds,
            "release_date": canonical.release_date.isoformat() if canonical.release_date else None,
            "thumbnail": thumb,
            "languages": [_language_entry(v.language) for v in by_language],
            "variants": {v.language: {"episode_id": v.id} for v in by_language},
        })
    entries.sort(key=lambda e: (e["episode_number"], e["title"]))
    return entries


def build(db: Session, storage: ObjectStorage) -> dict:
    art = _artwork_map(db, storage)
    shows = (
        db.query(Show)
        .filter(Show.status == "published")
        .options(selectinload(Show.seasons).selectinload(Season.episodes))
        .all()
    )

    catalog_shows: list[dict] = []
    for show in shows:
        if not show.section:
            continue  # a published show with no section has nowhere to go; the report flags it

        seasons_out, trailers_out = [], []
        languages: set[str] = set()
        episode_count = 0

        for season in sorted(show.seasons, key=lambda s: s.season_number):
            published = [e for e in season.episodes if e.status == "published"]
            if not published:
                continue
            grouped = _group_episodes(published, art)
            for entry in grouped:
                languages.update(lang["code"] for lang in entry["languages"])
            episode_count += len(grouped)
            if season.season_number == TRAILER_SEASON:
                trailers_out = grouped  # never rendered as a season
            else:
                seasons_out.append({
                    "season_number": season.season_number,
                    "title": season.title or f"Season {season.season_number}",
                    "episodes": grouped,
                })

        if not seasons_out:
            continue  # trailers alone are not a browsable show

        show_art = art.get(("show", show.id), {})
        catalog_shows.append({
            "slug": show.slug,
            "title": show.title.strip(),
            "synopsis": (show.synopsis or "").strip(),
            "category": show.category,
            "section": show.section,
            "featured": show.featured,
            "artwork": {
                "poster": show_art.get("poster"),
                "banner": show_art.get("banner"),
            },
            "languages": [_language_entry(c) for c in sorted(languages, key=lambda c: (c != "en", c))],
            "season_count": len(seasons_out),
            "episode_count": episode_count,
            "seasons": seasons_out,
            "trailers": trailers_out,
            # Flattened once at build time so search never walks the tree.
            "search_blob": " ".join(
                filter(None, [
                    show.title, show.category, show.section, show.synopsis,
                    *[e["title"] for s in seasons_out for e in s["episodes"]],
                ])
            ).lower(),
        })

    # Deterministic ordering: reference.json section order, then sort weight, then title.
    catalog_shows.sort(key=lambda s: (section_order(s["section"]), s["slug"]))
    ordered_by_weight = {s.slug: (s.sort_weight, s.title) for s in shows}
    catalog_shows.sort(
        key=lambda s: (section_order(s["section"]), ordered_by_weight[s["slug"]][0], s["title"], s["slug"])
    )

    sections_out: list[dict] = []
    for show in catalog_shows:
        if not sections_out or sections_out[-1]["name"] != show["section"]:
            sections_out.append({"name": show["section"], "shows": []})
        sections_out[-1]["shows"].append(show["slug"])

    hero = next((s for s in catalog_shows if s["featured"] and s["artwork"].get("banner")), None)
    if hero is None:
        hero = next((s for s in catalog_shows if s["artwork"].get("banner")), None)

    return {
        "schema_version": SCHEMA_VERSION,
        "hero": hero["slug"] if hero else None,
        "sections": sections_out,
        "shows": catalog_shows,
        "counts": {
            "shows": len(catalog_shows),
            "sections": len(sections_out),
            "episodes": sum(s["episode_count"] for s in catalog_shows),
            "trailers": sum(len(s["trailers"]) for s in catalog_shows),
        },
    }


def serialise(document: dict) -> bytes:
    """Stable bytes. sort_keys + fixed separators so the checksum only changes
    when the content changes."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def checksum(document: dict) -> str:
    return hashlib.sha256(serialise(document)).hexdigest()


def stamp(document: dict, run_id: str) -> dict:
    """Timestamps go on *after* checksumming, otherwise every build looks different."""
    return {**document, "run_id": run_id, "generated_at": datetime.now(UTC).isoformat()}
