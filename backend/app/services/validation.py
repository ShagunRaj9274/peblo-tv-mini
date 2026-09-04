"""The validation report: everything currently blocking a publish, grouped so a
content editor can work through it without asking an engineer.

Design choice: issues are grouped by *the thing you have to open to fix it*
(a show, an episode), not by rule name. Each issue carries a `fix` sentence and
a deep link the CMS turns into a button.
"""

from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from ..models import Artwork, Episode, Season, Show
from ..reference import TRAILER_SEASON, categories, languages, sections

BLOCKING = "blocking"
WARNING = "warning"


def _artwork_index(db: Session) -> dict[tuple[str, str], set[str]]:
    idx: dict[tuple[str, str], set[str]] = defaultdict(set)
    for owner_type, owner_id, kind in db.query(Artwork.owner_type, Artwork.owner_id, Artwork.kind):
        idx[(owner_type, owner_id)].add(kind)
    return idx


def collect_issues(db: Session) -> list[dict]:
    art = _artwork_index(db)
    issues: list[dict] = []

    shows = (
        db.query(Show)
        .options(selectinload(Show.seasons).selectinload(Season.episodes))
        .order_by(Show.title)
        .all()
    )

    seen_group_lang: dict[tuple[str, str], list[str]] = defaultdict(list)

    for show in shows:
        target = {"type": "show", "id": show.id, "title": show.title, "slug": show.slug}
        published_eps = [
            e for s in show.seasons for e in s.episodes
            if e.status == "published" and s.season_number != TRAILER_SEASON
        ]

        if show.status == "published":
            if not show.section:
                issues.append(_issue(
                    BLOCKING, "show_missing_section", target,
                    f"“{show.title}” is published but has no section, so there is no row to put it in.",
                    f"Open the show and pick one of: {', '.join(sections())}.",
                ))
            elif show.section not in sections():
                issues.append(_issue(
                    BLOCKING, "show_unknown_section", target,
                    f"“{show.title}” is in the section “{show.section}”, which isn't a section we ship.",
                    f"Change it to one of: {', '.join(sections())}.",
                ))
            if show.category and show.category not in categories():
                issues.append(_issue(
                    BLOCKING, "show_unknown_category", target,
                    f"“{show.title}” uses the category “{show.category}”, which isn't on the approved list.",
                    f"Pick one of: {', '.join(categories())}.",
                ))
            if not show.category:
                issues.append(_issue(
                    BLOCKING, "show_missing_category", target,
                    f"“{show.title}” has no category, so it can't be filtered in the viewer.",
                    "Open the show and choose a category.",
                ))
            missing_art = {"poster", "banner"} - art.get(("show", show.id), set())
            if missing_art:
                issues.append(_issue(
                    BLOCKING, "show_missing_artwork", target,
                    f"“{show.title}” is missing its {' and '.join(sorted(missing_art))} artwork.",
                    "Upload it on the show's Artwork tab. Poster is 600×900, banner is 1280×720.",
                ))
            if not published_eps:
                issues.append(_issue(
                    BLOCKING, "show_no_published_episodes", target,
                    f"“{show.title}” is published but has no published episodes outside trailers.",
                    "Publish at least one episode, or set the show back to draft.",
                ))
            if not (show.synopsis or "").strip():
                issues.append(_issue(
                    WARNING, "show_missing_synopsis", target,
                    f"“{show.title}” has no synopsis. The detail page will look empty.",
                    "Add a sentence or two describing the show.",
                ))

        for season in show.seasons:
            numbers: dict[int, list[Episode]] = defaultdict(list)
            for ep in season.episodes:
                if ep.status == "published":
                    numbers[ep.episode_number].append(ep)
            for number, eps in numbers.items():
                distinct_groups = {e.content_group for e in eps}
                if len(eps) > 1 and len(distinct_groups) > 1:
                    issues.append(_issue(
                        WARNING, "duplicate_episode_number",
                        {"type": "show", "id": show.id, "title": show.title, "slug": show.slug},
                        f"“{show.title}” season {season.season_number} has two different episodes "
                        f"numbered {number}: {', '.join(sorted(e.title for e in eps))}.",
                        "Renumber one of them so the viewer plays them in the right order.",
                    ))

            for ep in season.episodes:
                ep_target = {
                    "type": "episode", "id": ep.id, "title": ep.title, "slug": show.slug,
                    "show_title": show.title, "season": season.season_number,
                    "episode_number": ep.episode_number,
                }
                where = (
                    f"“{ep.title}” ({show.title}, "
                    + ("trailer" if season.season_number == TRAILER_SEASON
                       else f"S{season.season_number} E{ep.episode_number}")
                    + f", {ep.language})"
                )
                if ep.status != "published":
                    continue
                if not ep.duration_seconds:
                    issues.append(_issue(
                        BLOCKING, "episode_missing_duration", ep_target,
                        f"{where} has no duration, so we can't show a runtime or a progress bar.",
                        "Enter the runtime in minutes and seconds on the episode.",
                    ))
                if "thumbnail" not in art.get(("episode", ep.id), set()):
                    issues.append(_issue(
                        BLOCKING, "episode_missing_artwork", ep_target,
                        f"{where} has no thumbnail.",
                        "Upload a 640×360 thumbnail on the episode.",
                    ))
                if not ep.content_group:
                    issues.append(_issue(
                        BLOCKING, "episode_missing_content_group", ep_target,
                        f"{where} has no content group, so its language versions can't be linked.",
                        "Set a content group. Use the same value on every language of this episode.",
                    ))
                else:
                    seen_group_lang[(ep.content_group, ep.language)].append(where)
                if ep.language not in languages():
                    issues.append(_issue(
                        BLOCKING, "episode_unknown_language", ep_target,
                        f"{where} is tagged with the language “{ep.language}”, which we don't ship.",
                        f"Use one of: {', '.join(languages())}.",
                    ))
                if show.status != "published":
                    issues.append(_issue(
                        WARNING, "episode_published_show_draft", ep_target,
                        f"{where} is published but its show is {show.status}, so nobody will see it.",
                        f"Publish “{show.title}” when it's ready.",
                    ))

    for (group, lang), whos in seen_group_lang.items():
        if len(whos) > 1:
            issues.append(_issue(
                BLOCKING, "duplicate_group_language",
                {"type": "content_group", "id": group, "title": group},
                f"Two episodes claim to be the {lang} version of “{group}”: {'; '.join(whos)}.",
                "Keep one and delete or re-tag the other. A content group can only have one "
                "episode per language.",
            ))

    return issues


def _issue(severity: str, code: str, target: dict, problem: str, fix: str) -> dict:
    return {"severity": severity, "code": code, "target": target, "problem": problem, "fix": fix}


def report(db: Session) -> dict:
    issues = collect_issues(db)
    blocking = [i for i in issues if i["severity"] == BLOCKING]
    warnings = [i for i in issues if i["severity"] == WARNING]

    groups: dict[str, dict] = {}
    for issue in issues:
        t = issue["target"]
        key = f"{t['type']}:{t['id']}"
        groups.setdefault(key, {
            "target_type": t["type"],
            "target_id": t["id"],
            "title": t.get("show_title") and f"{t['show_title']} — {t['title']}" or t["title"],
            "slug": t.get("slug"),
            "issues": [],
        })["issues"].append(issue)

    ordered = sorted(
        groups.values(),
        key=lambda g: (0 if any(i["severity"] == BLOCKING for i in g["issues"]) else 1, g["title"]),
    )

    return {
        "can_publish": not blocking,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "summary": _summary(blocking, warnings),
        "groups": ordered,
    }


def _summary(blocking: list[dict], warnings: list[dict]) -> str:
    if not blocking and not warnings:
        return "Everything checks out. You're clear to publish."
    if not blocking:
        return (f"Clear to publish. {len(warnings)} thing"
                f"{'s' if len(warnings) != 1 else ''} worth a look first.")
    n = len({i["target"]["id"] for i in blocking})
    return (f"{len(blocking)} problem{'s' if len(blocking) != 1 else ''} across {n} item"
            f"{'s' if n != 1 else ''} must be fixed before publishing.")
