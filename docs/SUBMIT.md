# Getting this into GitHub and onto the form

## 1. Push it

```bash
cd peblo-tv-mini
git init -b main
git add .
git commit -m "Peblo TV Mini: CMS, publish pipeline, viewer"
```

Create an **empty public repo** on GitHub (no README, no .gitignore — this repo has both),
then:

```bash
git remote add origin https://github.com/<you>/peblo-tv-mini.git
git push -u origin main
```

CI runs on push. Wait for it to go green before you submit — the `stack` job takes about
four minutes because it builds and boots the whole compose stack. If a recruiter clicks
one thing, it's that checkmark.

## 2. Verify from a clean clone

Do this in a different directory. It catches the classic "works because of a file I never
committed."

```bash
git clone https://github.com/<you>/peblo-tv-mini.git /tmp/verify
cd /tmp/verify
docker compose up --build
```

Then check all four:

- http://localhost:5174 — viewer has a hero and populated rows
- http://localhost:5173 — CMS login works
- http://localhost:8000/health/ready — `"status": "ok"`
- http://localhost:8000/catalog — `counts.shows` is greater than zero

```bash
docker compose down -v
```

## 3. Record the demo

Follow `docs/DEMO.md`. Export as `YourName_FullstackDeveloper.mp4`.

## 4. Fill in the form

| Field | What to paste |
|---|---|
| GitHub repository link | `https://github.com/<you>/peblo-tv-mini` |
| Screen recording | upload `YourName_FullstackDeveloper.mp4` |
| Assessment (README) link | `https://github.com/<you>/peblo-tv-mini/blob/main/README.md` |

Review, then submit.

## Before you do

Two things in the README are placeholders and should not go out as written:

1. **The time table.** Replace with your actual hours.
2. **The "AI tools" paragraph.** The brief asks where you accepted or rejected AI output.
   Read the code, decide what you'd have done differently, and write that section yourself.

Also worth doing: skim `README.md` § "Decisions I made where the brief was ambiguous" and
make sure you agree with every one. You'll be asked about at least one of them, and
"because that's what it does" is a worse answer than disagreeing with it.
