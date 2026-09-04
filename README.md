# Peblo TV Mini

CMS upload → published catalogue → Netflix-style browse.

Three layers and the pipeline that runs them: a FastAPI + Postgres API, an internal CMS,
and a viewer that reads only the published catalogue file.

---

## Run it

```bash
git clone <this-repo> && cd peblo-tv-mini
docker compose up --build
```

Nothing else. No `.env` needed — compose has working defaults for every variable
(`.env.example` documents all of them). The API waits for Postgres, applies migrations,
imports the seed data, and runs one publish, so the viewer has content on first load.

| | URL | |
|---|---|---|
| Peblo TV (viewer) | http://localhost:5174 | no login |
| CMS | http://localhost:5173 | `admin@peblo.tv` / `peblo-admin` |
| CMS as an editor | http://localhost:5173 | `editor@peblo.tv` / `peblo-editor` — same access, **cannot publish** |
| API docs | http://localhost:8000/docs | |
| Readiness | http://localhost:8000/health/ready | |

```bash
make test     # 36 backend tests, ~9s, no database needed
make lint     # ruff + tsc on both frontends
make reset    # wipe volumes and start clean
```

### About the seed data

`seed_shows.json`, `reference.json` and `assets/` were not attached to the brief I
received, so `scripts/make_seed.py` generates spec-faithful stand-ins: 95 episode rows
across 8 shows, with thirteen deliberate defects seeded in (a `"11:20"` duration, a
negative runtime, a duplicate `content_group`+language pair, an unapproved category, a
missing section, a stray `en-IN` language, a duplicated episode number, an episode with no
content group, and a date in `DD-MM-YYYY`).

**To use the real files: drop them into `data/` and `assets/` and re-run `make reset`.**
Nothing in the application code reads the generator — the API loads `reference.json` at
runtime and the seeder reads `seed_shows.json` at import. No code changes needed.

---

## What each layer does

```
CMS (React) ──► API (FastAPI + Postgres) ──► publish ──► catalog/runs/<run_id>.json
   :5173                :8000                              + catalog/current.pointer
                                                                    │
                            Viewer (React) :5174 ◄── GET /catalog ──┘
```

### Part A — Backend

- `shows → seasons → episodes`, plus `artwork`, `publish_runs`, `audit_log`. One Alembic
  migration; CI applies it up, down and up again.
- **Artwork upload** at `POST /admin/artwork/{owner_type}/{owner_id}/{kind}`. Poster (2:3,
  600×900) and banner (16:9, 1280×720) belong to a show; thumbnail (16:9, 640×360) belongs
  to an episode, because that is the surface each one is cut for. Aspect ratio, dimensions
  and the 200 KB ceiling are all checked server-side, and **every** problem comes back at
  once so an editor fixes the image in one pass.
- **CRUD** with the brief's three rules enforced: an episode can't be published without
  artwork and a duration, `(content_group, language)` is unique *at the database level*,
  and a published show must have a section.
- `POST /admin/catalog/publish` — atomic, recorded, idempotent (see Part E).
- `GET /catalog`, `GET /catalog/search`, `GET /catalog/shows/{slug}` — the read side.
- `GET /admin/validation-report` — grouped by the thing you have to open to fix it.
- Roles: `require_role` reads the **database row**, not the JWT claim, so a demotion takes
  effect on the next request rather than when the token expires.

### Part B — CMS

Shows list with search, filters (section, status, language) and pagination. Show editor
with three labelled artwork slots — each showing its required size, a live preview and the
server's rejection text verbatim. Publish page with the validation report, a publish
button that is disabled with the reason on hover, a dry-run diff, and run history with
rollback.

Loading, empty, error and permission-denied all go through one shared component set, so
they can't drift apart screen to screen. TanStack Query throughout; retries are disabled
for 401/403 because those don't fix themselves.

### Part C — Viewer

Hero using the banner, rows by section using posters, episode lists using thumbnails.
Search and filters that are populated from what's actually in the catalogue, so you can
never pick a filter that returns nothing. Grouped episodes render as one row with a
language picker. Season 0 gets its own trailer strip and never appears as a season tab.

Slow images: every image sits in a box that already reserves its aspect ratio, filled with
a colour derived from the slug, and the real image fades in when it decodes. Offscreen
rows are lazy. Nothing shifts when an image lands.

### Part D — Pipeline

`docker-compose up` brings up all four services. CI lints, tests, applies migrations both
directions, typechecks and builds both frontends, **brings the whole stack up and smoke
tests it** (including asserting that an editor token gets a 403 from publish), builds
SHA-tagged images, and has a written deploy job behind a manual approval gate.

---

## Part E — Written

### How publishing is atomic, and what happens if it dies mid-publish

The publish never writes to the file anyone is reading. It:

1. builds the document in memory and checksums it;
2. writes it to an **immutable, run-scoped key** — `catalog/runs/<run_id>.json`. Nothing
   points at this key yet, so a partial write is invisible;
3. flips one small pointer object, `catalog/current.pointer`, to name that key.

Readers resolve the pointer, then fetch the immutable key. They therefore see either the
whole previous catalogue or the whole new one, and the file they are reading can never
change underneath them. Step 3 is the only mutation, and it is atomic in both backends:
on local disk it is `write to temp → fsync → os.replace → fsync the directory`; on R2 it
is a single `PUT`, which S3-compatible stores make all-or-nothing.

**If the process dies mid-publish:** the pointer was never touched, so the live catalogue
is still the last good one and the viewer notices nothing. The run row is left as
`running` and gets swept to `failed` on the next startup and before the next publish, with
an error explaining that the live catalogue was not changed. The half-written run file is
orphaned garbage — it is never named by anything, and it is kept deliberately, because an
operator debugging a bad publish wants to look at it. A retention job would delete run
files older than N days, keeping the last ~20 for rollback.

`test_publish_is_atomic_the_pointer_flips_only_at_the_end` proves this: it monkeypatches
storage to raise mid-write, then asserts the pointer is unchanged, the served catalogue is
byte-identical to before, and the run recorded as `failed`.

Publishing is also **idempotent**: because the document is serialised with sorted keys and
timestamps are stamped on *after* checksumming, the same database state produces the same
checksum. A second publish with nothing changed returns `no_changes`, reuses the existing
key, and does not churn the pointer or any CDN cache. And one publish runs at a time,
guarded by a Postgres advisory lock.

### The storage abstraction: what changes to move to Cloudflare R2

One environment variable. `STORAGE_BACKEND=r2` plus the four `R2_*` values — `R2Storage`
is already written in `backend/app/storage/r2.py`.

That's true because of two constraints the abstraction enforces. First, nothing outside
`app/storage/` ever builds a path or a key by hand; callers pass logical keys and ask for
`public_url()`. Second, "which catalogue is live" is modelled as a **pointer object**
rather than a mutable file — which is the only design that is atomic on both a POSIX
filesystem and an object store, since S3 has no rename.

Three real things would still need attention, and I'd rather name them than claim it's
free:

- **Artwork URLs are baked into the published catalogue.** Moving buckets changes every
  URL in it, so the migration is: copy objects → point `R2_PUBLIC_BASE_URL` at the CDN →
  republish. Republishing is cheap and atomic, so this is a non-event, but you have to
  remember to do it.
- **`public_url` is unsigned.** Fine for a public catalogue behind a CDN; if artwork ever
  needed to be private it becomes presigned URLs with an expiry, which changes the caching
  story.
- **Local disk silently gives you read-after-write consistency.** R2 does too, so this is
  safe — but on a store that didn't, the pointer flip would need a version check.

### Search: how it works, where it breaks, what's next

Search is a linear scan over the in-process cached catalogue snapshot, against a
`search_blob` that the publish job flattens once at build time (show title + category +
section + synopsis + every episode title). `q` matches all three of the required fields;
`category`, `language` and `section` compose as AND filters; results are ranked in tiers
(exact title, prefix, substring, category, episode-only).

**Where it stops working.** The current catalogue is 37 KB and 7 shows. Scanning it is
tens of microseconds — genuinely faster than a database round trip. It holds up to roughly
**5,000 shows / a few MB**, at which point two things break at once: the snapshot is too
big to want in every API process's memory, and per-request scanning starts showing up in
p99. It also can't do the things people actually expect from search well before that
point: no stemming ("stories" vs "story"), no typo tolerance, no relevance beyond my tier
heuristic, and no Hindi tokenisation, which matters for a bilingual catalogue.

**What I'd do next**, in the order I'd actually do it: (1) move search to Postgres, writing
a denormalised `published_catalog_entries` table as part of the publish transaction, with a
`tsvector` GIN index and `pg_trgm` for typo tolerance — this keeps the read path off the
live content tables, which was the point, and gets you stemming and real ranking for a
day's work; (2) at the point where you want multilingual analysers, synonyms and per-child
personalised ranking, move to OpenSearch, fed by the same publish job. I would not reach
for step 2 early — a search index that can disagree with the catalogue is a new class of
bug, and Postgres in the same transaction cannot.

### Why serve a pre-published file at all, and where that bites

Three reasons. **Blast radius**: the viewer is the surface children see, and it cannot be
taken down by a slow query, a bad migration or an editor mid-edit — it reads a static file.
**Editorial control**: content teams want to prepare a batch and make it live at a moment
they choose, which a query-per-request model doesn't give you without a second "published"
flag on everything anyway. **Cost and latency**: it's one immutable file, so it caches at
the CDN edge forever and most requests never reach the API.

**Where it bites**, honestly:

- **Staleness is now a real state.** Between an editor's save and someone pressing Publish,
  the CMS and the viewer disagree, and that confuses people — which is why the publish page
  has a dry-run diff showing exactly what would change.
- **Everything is all-or-nothing.** A one-word typo fix requires republishing the whole
  catalogue. Fine at this size; at 50,000 shows the build time becomes the bottleneck and
  you'd want per-section files with a manifest, or incremental builds.
- **Personalisation can't live in it.** "Continue Watching" is in `reference.json` as a
  section, and it fundamentally cannot come from a shared file — it has to be a per-user
  API call merged client-side. The published catalogue is the *shared* layer only.
- **Two sources of truth for reads.** The validation report queries Postgres; the viewer
  reads the file. They can disagree, and reasoning about a bug means checking which one
  you're looking at.

### What I left out, and why

- **No video.** The brief is about catalogue plumbing, and a player would have been the
  most visible work with the least judgment in it.
- **No refresh tokens.** A 12-hour JWT for an internal tool used by a handful of editors.
  Refresh-token rotation is real work and would have bought nothing here.
- **Frontend tests.** All my test budget went to the backend, where the risk is — an
  atomicity bug corrupts the product for everyone, a CMS layout bug annoys one editor.
  If I had another hour it would go to a Playwright test of upload-reject → fix → publish.
- **Bulk episode import in the CMS.** The seeder does it; an editor can't. That's the
  first thing I'd build next, since it's obviously what "50 times a week" implies.
- **Per-section catalogue files**, for the reasons above — premature at this size.
- **`Continue Watching`** is in the reference sections but has no viewer implementation,
  since there are no user accounts on the viewer side.

### AI tools

I used Claude throughout, mostly as a fast typist and a rubber duck. Where I took its
output: the boilerplate — Pydantic schemas, the Alembic migration mirroring the models,
the repetitive CMS form JSX, the CSS. Where I rejected it: its first instinct for publish
was to write `catalog.json` and swap it with a temp file rename, which works on one disk
and silently isn't atomic on S3 — the pointer-object design is the fix, and it's the whole
reason the R2 swap is one class. It also wanted to validate artwork in the browser and
trust it on the server, and it initially wrote the role check against the JWT claim rather
than the user row. The error copy is mine: models write "Validation failed for field
artwork", and the person reading it needs to be told to crop rather than stretch.

---

## Operability

### Health

- `GET /health` — liveness. Deliberately dependency-free, so a slow database can't get the
  container killed and restarted into the same slow database.
- `GET /health/ready` — readiness. Checks Postgres, checks that the storage pointer
  resolves to a file that exists, and reports the catalogue's counts. Returns 503 when
  degraded, which is what the load balancer keys off.

### The one thing I'd alert on

**Catalogue age: time since the last successful publish run, alerting above 24 hours during
a weekday.**

Not error rate, and not the publish job's own failures — those are already loud, because a
failed publish shows up in the run history in front of the person who pressed the button.
The dangerous failure is the *quiet* one: publishing is broken, or blocked by a validation
issue nobody has looked at, and the site keeps serving yesterday's catalogue perfectly.
Every dashboard stays green. Latency is fine, error rate is zero, health checks pass — the
system is serving a stale file exactly as designed. The content team notices days later
when a show they shipped on Monday still isn't live.

That's the alert that catches a whole class of problems (broken publish, stuck validation,
storage permissions, a pointer never flipped) with one number that maps directly to the
thing the business cares about: is what we made actually reaching children. I'd pair it
with a cheap page on `/health/ready` returning 503 for more than two minutes.

### Secrets in production

Nothing in `.env.example` is real, and `.env` is gitignored. In production I would not use
env files at all:

- **Cloud secret manager** (AWS Secrets Manager / Google Secret Manager) holds
  `JWT_SECRET`, the database password and the R2 keys. The container reads them at boot
  through its task role — they are never in the image, never in compose, never in CI logs.
- **No long-lived cloud credentials in GitHub.** The deploy job assumes a role via OIDC and
  mints a short-lived token, so there is no static AWS key to leak or rotate.
- **Rotation:** the database password and R2 keys rotate on a schedule with a dual-key
  overlap window. `JWT_SECRET` is the awkward one — rotating it signs every editor out.
  That's an acceptable blast radius for a handful of internal users, and it's the reason I
  didn't build refresh tokens; the moment there are hundreds of editors, that changes.
- **Non-secrets stay in plain config** (`CORS_ORIGINS`, `STORAGE_BACKEND`, bucket names).
  Putting them in the secret store makes real secrets harder to see.
- One thing to watch: `VITE_API_BASE_URL` is inlined into the frontend bundle at build
  time. That is fine because it is a public URL — but it means **no secret can ever go in a
  `VITE_*` variable**, and that is worth saying out loud, because it is the mistake
  everyone makes once.

---

## Stretch goals

All three were done, and none of them at the expense of the core:

- **Versioned catalogue with rollback** — every run writes its own immutable file, so
  rollback is the same atomic pointer flip as publish. No rebuild, so it can't fail
  halfway. Button is in the CMS publish history.
- **Publish dry-run with a diff** — "Preview changes" shows which shows would appear,
  update or disappear, computed against the live file.
- **Audit log** — who changed what, at `GET /admin/audit-log`, written on every CRUD and
  upload.

---

## Time spent

| Part | Hours |
|---|---|
| A — backend, publish, tests | 5.0 |
| B — CMS | 3.0 |
| C — viewer | 2.5 |
| D — compose, CI, ops | 1.5 |
| E — README | 1.0 |
| **Total** | **~13** |

## Decisions I made where the brief was ambiguous

- **Posters/banners hang off shows, thumbnails off episodes.** The brief lists three sizes
  without saying what owns what; this matches the surfaces it describes.
- **A published show with no section is skipped by the build**, not failed. The validation
  report flags it as blocking, so it can't reach a normal publish — but the build stays
  total so a `--force` publish can never produce a broken document.
- **Trailers alone don't make a browsable show.** A show whose only published episodes are
  Season 0 is left out of the catalogue.
- **Ungrouped episodes still ship**, keyed by their own id, rather than vanishing. Silently
  dropping content is worse than shipping it un-grouped, and the report flags it.
- **The seeder quarantines rather than cleans.** Formatting differences (`"11:20"`,
  `DD-MM-YYYY`) are normalised and logged; content decisions (unknown category, duplicate
  variant) import as drafts with a note, so an editor decides. An import that silently
  fixes bad data hides the problem from the people who own it.
- **English is the canonical language variant** when collapsing a content group, falling
  back to alphabetically-first. It has to be deterministic or the catalogue churns.
