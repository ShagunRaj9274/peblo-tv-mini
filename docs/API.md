# API reference

Base URL `http://localhost:8000`. Interactive docs at `/docs`.

## Auth

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/auth/login` | — | `{email, password}` → JWT |
| GET | `/auth/me` | any | current user |

Send `Authorization: Bearer <token>`. Roles are checked against the **database row**,
not the token claim.

## Viewer (public, no auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/catalog` | the published catalogue; `ETag`, `Cache-Control: max-age=60` |
| GET | `/catalog/search` | `?q=&category=&language=&section=` — all compose as AND |
| GET | `/catalog/shows/{slug}` | one show from the published file |

These three never touch the content tables. The viewer app calls nothing else.

## Content (editor or admin)

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/reference` | sections, categories, languages, artwork specs |
| GET | `/admin/shows` | `?q=&section=&status=&language=&page=&page_size=` |
| POST | `/admin/shows` | creates season 0 (trailers) and season 1 automatically |
| GET/PATCH/DELETE | `/admin/shows/{id}` | |
| POST | `/admin/shows/{id}/seasons` | |
| GET | `/admin/shows/{id}/episodes` | |
| POST | `/admin/episodes` | 409 on duplicate `(content_group, language)` |
| PATCH/DELETE | `/admin/episodes/{id}` | |
| GET | `/admin/audit-log` | |

## Artwork (editor or admin)

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/artwork/specs` | |
| POST | `/admin/artwork/{owner_type}/{owner_id}/{kind}` | multipart `file` |
| DELETE | `/admin/artwork/{id}` | |

`owner_type` is `show` (kinds: `poster`, `banner`) or `episode` (kind: `thumbnail`).

A rejection is a 422 shaped for the UI to render directly:

```json
{
  "detail": {
    "message": "We can't use this image yet.",
    "problems": [
      {
        "code": "bad_aspect_ratio",
        "message": "Poster must be 2:3 (like 600×900). This image is 900×900, which is the wrong shape — crop it rather than stretching it.",
        "expected": "2:3",
        "actual": "900×900"
      }
    ]
  }
}
```

Every failing rule is returned at once, so an editor fixes the image in one pass.

## Publish

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/admin/validation-report` | editor | grouped by what you must open to fix it |
| POST | `/admin/catalog/dry-run` | editor | report + diff against live; writes nothing |
| POST | `/admin/catalog/publish` | **admin** | 409 with the report when blocked, 423 when one is already running |
| GET | `/admin/catalog/runs` | editor | run history |
| POST | `/admin/catalog/rollback/{run_id}` | **admin** | re-points at an earlier immutable file |

## Ops

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness; no dependencies |
| GET | `/health/ready` | database + storage + catalogue; 503 when degraded |

## Catalogue shape

```jsonc
{
  "schema_version": 1,
  "run_id": "…", "generated_at": "…",
  "hero": "kabir-and-the-kite",
  "sections": [{ "name": "New on Peblo", "shows": ["mango-and-moon"] }],
  "shows": [{
    "slug": "…", "title": "…", "category": "…", "section": "…",
    "artwork": { "poster": {...}, "banner": {...} },
    "languages": [{ "code": "en", "label": "English" }],
    "seasons": [{ "season_number": 1, "title": "Season 1", "episodes": [{
      "content_group": "…",
      "languages": [{ "code": "en" }, { "code": "hi" }],  // collapsed variants
      "variants": { "en": { "episode_id": "…" }, "hi": { "episode_id": "…" } },
      "thumbnail": {...}
    }]}],
    "trailers": [ /* season 0, never a season tab */ ]
  }]
}
```

Sections are ordered by `reference.json`; shows by sort weight, then title, then slug.
The document is serialised with sorted keys so the same database state produces the same
checksum — that's what makes publish idempotent.
