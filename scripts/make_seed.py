"""Generates data/seed_shows.json: 95 episode rows across 8 shows, deliberately imperfect.

Only used to stand in for the official seed file. If you have the real
seed_shows.json, overwrite data/seed_shows.json and delete this script.
"""

import json
import pathlib

SHOWS = [
    ("mango-and-moon", "Mango & Moon", "Preschool", "New on Peblo", "A round little cat and her patient moon walk home through eight kinds of weather."),
    ("the-tinkering-twins", "The Tinkering Twins", "Educational", "Learn Along", "Two siblings, one shed, and a rule that nothing gets thrown away before it is understood."),
    ("river-of-rhymes", "River of Rhymes", "Music", "Stories & Rhymes", "Nursery rhymes carried downstream by a boat that only floats when everyone sings."),
    ("kabir-and-the-kite", "Kabir and the Kite", "Adventure", "Made in India", "A boy from Ahmedabad follows his runaway kite across rooftops, railways and one very long afternoon."),
    ("deep-blue-detectives", "Deep Blue Detectives", "Mystery", "Big Kid Adventures", "Three reef friends solve the small crimes of a very busy lagoon."),
    ("grandma-banyans-garden", "Grandma Banyan's Garden", "Nature", "Learn Along", "Every episode plants one seed and waits, honestly, for it to grow."),
    ("robot-tiffin-service", "Robot Tiffin Service", "Comedy", "Made in India", "A delivery robot with no sense of smell tries to run a lunch route in Mumbai."),
    ("the-paper-kingdom", "The Paper Kingdom", "Fantasy", "Big Kid Adventures", "A folded paper crown opens a kingdom that rearranges itself whenever someone tells the truth."),
]

TITLES = [
    "The First Loud Morning", "Something Under the Steps", "A Very Slow Race", "The Borrowed Umbrella",
    "Ten Ways to Say Hello", "The Upside-Down Map", "Nobody's Lunch", "The Quiet Contest",
    "A Knot That Won't Untie", "The Longest Shortcut", "Two Left Shoes", "The Wrong Bus Home",
    "Counting to Almost", "The Second Best Idea", "A Song for Tuesdays",
]

rows = []
ep_id = 1


def add(**kw):
    global ep_id
    row = {
        "episode_id": f"ep-{ep_id:03d}",
        "show_slug": kw["slug"],
        "show_title": kw["show_title"],
        "show_synopsis": kw["synopsis"],
        "category": kw["category"],
        "section": kw["section"],
        "season_number": kw["season"],
        "season_title": kw.get("season_title") or (f"Season {kw['season']}" if kw["season"] else "Trailers"),
        "episode_number": kw["ep_no"],
        "title": kw["title"],
        "synopsis": kw.get("ep_synopsis", ""),
        "duration_seconds": kw.get("duration", 660),
        "language": kw.get("language", "en"),
        "content_group": kw["content_group"],
        "status": kw.get("status", "published"),
        "release_date": kw.get("release_date", "2025-04-14"),
    }
    rows.append(row)
    ep_id += 1


for si, (slug, title, category, section, synopsis) in enumerate(SHOWS):
    base = dict(slug=slug, show_title=title, synopsis=synopsis, category=category, section=section)
    # Season 0 — trailers
    add(**base, season=0, ep_no=1, title=f"{title} — Trailer", duration=75,
        content_group=f"{slug}-trailer", ep_synopsis="A 75 second look at the show.")
    if si % 2 == 0:  # half the shows ship a Hindi trailer too
        add(**base, season=0, ep_no=1, title=f"{title} — Trailer (Hindi)", duration=75,
            language="hi", content_group=f"{slug}-trailer", ep_synopsis="A 75 second look at the show.")
    n_eps = [6, 5, 6, 5, 5, 4, 5, 4][si]
    for e in range(1, n_eps + 1):
        cg = f"{slug}-s1e{e}"
        t = TITLES[(si * 3 + e) % len(TITLES)]
        add(**base, season=1, ep_no=e, title=t, content_group=cg,
            duration=540 + (e * 37) % 300,
            ep_synopsis=f"{t}. Episode {e} of season 1.")
        # Hindi variants for most episodes on Indian-section shows and every 2nd elsewhere
        if section == "Made in India" or e % 2 == 1:
            add(**base, season=1, ep_no=e, title=t, content_group=cg, language="hi",
                duration=540 + (e * 37) % 300, ep_synopsis=f"{t}. Episode {e} of season 1.")
    if si < 5:  # five shows have a second season
        for e in range(1, 4):
            cg = f"{slug}-s2e{e}"
            t = TITLES[(si * 5 + e + 7) % len(TITLES)]
            add(**base, season=2, ep_no=e, title=t, content_group=cg,
                duration=600 + (e * 41) % 200, release_date="2025-11-02",
                ep_synopsis=f"{t}. Episode {e} of season 2.")

# ---------------------------------------------------------------- defects
# 1. missing duration
rows[4]["duration_seconds"] = None
# 2. duration as a "MM:SS" string instead of seconds
rows[9]["duration_seconds"] = "11:20"
# 3. negative duration
rows[17]["duration_seconds"] = -300
# 4. duplicate (content_group, language) — exact collision
dup = dict(rows[12])
dup["episode_id"] = "ep-901"
dup["title"] = rows[12]["title"] + " "
rows.append(dup)
# 5. category not in reference.json
rows[21]["category"] = "Edutainment"
# 6. language not in reference.json
rows[26]["language"] = "en-IN"
# 7. missing section on a show that is marked published
for r in rows:
    if r["show_slug"] == "the-paper-kingdom":
        r["section"] = ""
# 8. whitespace / casing noise in titles
rows[30]["title"] = "  " + rows[30]["title"].upper() + "  "
# 9. episode with no content_group at all
rows[35]["content_group"] = None
# 10. duplicate episode_number within the same season
clash = dict(rows[40])
clash["episode_id"] = "ep-902"
clash["content_group"] = clash["content_group"] + "-alt"
clash["title"] = "The Repeated Number"
rows.append(clash)
# 11. a few drafts that must not reach the catalogue
for i in (3, 44, 60):
    rows[i]["status"] = "draft"
# 12. status value nobody defined
rows[52]["status"] = "in_review"
# 13. release date in a different format
rows[55]["release_date"] = "14-04-2025"

out = pathlib.Path(__file__).resolve().parents[1] / "data" / "seed_shows.json"
out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
print(f"{len(rows)} episode rows across {len({r['show_slug'] for r in rows})} shows -> {out}")
