from .helpers import build_show


def setup_catalog(client, admin):
    build_show(client, admin, "mango", section="New on Peblo", category="Comedy",
               languages=("en", "hi"))
    build_show(client, admin, "tinkering-twins", section="Learn Along", category="Educational",
               languages=("en",))
    client.post("/admin/catalog/publish", headers=admin)


def test_search_matches_show_title(client, admin):
    setup_catalog(client, admin)
    r = client.get("/catalog/search?q=mango").json()
    assert [s["slug"] for s in r["results"]] == ["mango"]


def test_search_matches_episode_title(client, admin):
    setup_catalog(client, admin)
    r = client.get("/catalog/search?q=loud morning").json()
    assert r["count"] == 2  # both shows use the same episode title in the helper


def test_search_matches_category(client, admin):
    setup_catalog(client, admin)
    r = client.get("/catalog/search?q=educational").json()
    assert [s["slug"] for s in r["results"]] == ["tinkering-twins"]


def test_filters_compose(client, admin):
    setup_catalog(client, admin)
    both = client.get("/catalog/search?language=en").json()
    assert both["count"] == 2
    hindi = client.get("/catalog/search?language=hi").json()
    assert [s["slug"] for s in hindi["results"]] == ["mango"]
    narrowed = client.get("/catalog/search?language=hi&category=Educational").json()
    assert narrowed["count"] == 0
    combined = client.get("/catalog/search?q=mango&section=New+on+Peblo&language=hi").json()
    assert combined["count"] == 1


def test_search_is_case_and_accent_insensitive(client, admin):
    setup_catalog(client, admin)
    assert client.get("/catalog/search?q=MANGO").json()["count"] == 1


def test_empty_result_is_a_clean_zero_not_an_error(client, admin):
    setup_catalog(client, admin)
    r = client.get("/catalog/search?q=zzzzz")
    assert r.status_code == 200
    assert r.json() == {"query": {"q": "zzzzz", "category": None, "language": None,
                                  "section": None}, "count": 0, "results": []}


def test_validation_report_groups_by_the_thing_you_have_to_fix(client, editor):
    client.post("/admin/shows", json={"slug": "broken", "title": "Broken Show"}, headers=editor)
    from app.db import SessionLocal
    from app.models import Show
    with SessionLocal() as db:
        show = db.query(Show).filter(Show.slug == "broken").one()
        show.status = "published"
        db.commit()

    report = client.get("/admin/validation-report", headers=editor).json()
    assert report["can_publish"] is False
    assert report["blocking_count"] >= 3
    group = next(g for g in report["groups"] if g["slug"] == "broken")
    codes = {i["code"] for i in group["issues"]}
    assert {"show_missing_section", "show_missing_artwork", "show_no_published_episodes"} <= codes
    for issue in group["issues"]:
        assert issue["fix"], "every issue needs an actionable fix sentence"


def test_report_is_clean_for_a_healthy_catalogue(client, admin):
    build_show(client, admin, "mango")
    report = client.get("/admin/validation-report", headers=admin).json()
    assert report["can_publish"] is True


def test_catalog_is_empty_before_first_publish(client):
    body = client.get("/catalog").json()
    assert body["shows"] == []
    assert "Nothing has been published" in body["message"]
