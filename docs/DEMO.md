# Demo script — screen recording

Target length: **5–7 minutes**. Record at 1920×1080. Don't rehearse it into a sales pitch;
narrate what you're doing and why, the way you would in a code review.

Before you hit record:

```bash
make reset        # clean database, fresh seed, one auto-publish
```

Wait for `Initial publish: success` in the logs, then open both tabs.

---

## Shot 1 — The viewer, 45s

http://localhost:5174

- Home screen: hero, then scroll through the section rows.
- Say out loud: *"Hero uses the banner, rows use the poster, episode lists use the
  thumbnail — three different crops for three different surfaces."*
- Open **Kabir and the Kite**.
- Point at the trailer strip: *"Season 0 is trailers by convention, so it gets its own
  strip and never appears as a season tab."*
- Point at an episode with two language chips: *"These two rows in the source data share a
  content group, so the catalogue collapses them into one entry with a language picker."*
- Search "kite", then apply the Hindi + category filters. Then search something that
  doesn't exist to show the empty state.

## Shot 2 — Upload validation, 90s  ← *the money shot*

http://localhost:5173, sign in as **admin@peblo.tv / peblo-admin**.

Open any show → Artwork.

- Upload `assets/poster_wrong_ratio.jpg` into the **Poster** slot. Read the error aloud —
  it names the required ratio, the actual size, and says to crop rather than stretch.
- Upload `assets/banner_too_big.png` into the **Banner** slot. It's 2.5 MB: the error
  names the limit and suggests Squoosh.
- Open an episode → upload `assets/thumb_tiny.jpg` → rejected as too small.
- Now upload the matching `*_good.jpg` for each. Preview appears, "Saved."
- Say: *"All three of those checks are server-side. The browser copy is a courtesy —
  curl gets the same 422."* Optionally show it:

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@peblo.tv","password":"peblo-admin"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -X POST "localhost:8000/admin/artwork/show/<SHOW_ID>/poster" \
  -H "Authorization: Bearer $TOKEN" -F "file=@assets/poster_wrong_ratio.jpg" | python3 -m json.tool
```

## Shot 3 — Breaking publish on purpose, 75s

- Open an episode, clear its runtime to `0 min 0 sec`, save.
- Go to **Publish**. The report has gone red, the button is disabled, and the issue is
  grouped under that show with a fix sentence and an "Open show" button.
- Click through, restore the runtime, come back. Report goes green.

## Shot 4 — Roles actually enforced, 30s

- Sign out, sign in as **editor@peblo.tv / peblo-editor**.
- Publish page still loads — an editor needs to *see* what's blocking.
- Publish button is disabled with the banner explaining why.
- Say: *"The role check reads the database row, not the token claim, so a demotion takes
  effect on the next request."*

## Shot 5 — Publishing, 90s

Back as admin.

- **Preview changes** first: the dry run lists what would appear or update.
- **Publish catalogue.** Show the run appearing in history with who, when, counts and the
  file name.
- Press **Publish** again immediately → `no changes`. Say: *"Idempotent. Same database
  state, same checksum, so it doesn't churn the pointer or the CDN cache."*
- Refresh the viewer to show the change is live.
- Optionally: **Roll back to this** on an earlier run, refresh the viewer, roll forward.

Show the atomicity in the terminal if you have time:

```bash
docker compose exec api ls -la /data/storage/catalog/runs/
docker compose exec api cat /data/storage/catalog/current.pointer
```

*"Each run writes its own immutable file. Publishing flips that one pointer. A reader sees
the whole old catalogue or the whole new one — never a half-written file."*

## Shot 6 — Operability, 45s

```bash
curl -s localhost:8000/health/ready | python3 -m json.tool
make test
```

- Point at `test_publish_is_atomic_the_pointer_flips_only_at_the_end` in the output.
- Show `.github/workflows/ci.yml` — specifically the `stack` job that brings compose up in
  CI and asserts an editor gets a 403.
- Close on the README's alerting section: *"The one thing I'd alert on is catalogue age,
  because a broken publish is a silent failure — every dashboard stays green while the site
  serves yesterday."*

---

## Export

Name the file exactly as the form requires:

```
YourName_FullstackDeveloper.mp4
```

MP4, H.264. Keep it under ~200 MB — if your recorder outputs something huge:

```bash
ffmpeg -i raw.mov -vcodec libx264 -crf 26 -preset medium -acodec aac \
  YourName_FullstackDeveloper.mp4
```

---

## Pre-submit checklist

- [ ] `docker compose down -v && docker compose up --build` works from a clean clone
- [ ] `make test` → 36 passed
- [ ] `make lint` → clean
- [ ] Real `seed_shows.json` / `reference.json` / `assets/` dropped into `data/` and
      `assets/` if you have them
- [ ] README time table edited to your actual hours
- [ ] **README "AI tools" paragraph rewritten in your own words** — see note below
- [ ] Repo is public, or access shared
- [ ] GitHub Actions has run green on `main` (the badge is the first thing they'll click)
- [ ] Video named `YourName_FullstackDeveloper.mp4`

> **On the AI-tools paragraph:** the brief explicitly asks where you accepted or rejected
> AI output. That answer has to be yours. Read the code, form your own view of what you'd
> have done differently, and rewrite that section before submitting — a Part E that doesn't
> sound like the person in the interview is the one thing this repo can't defend for you.
