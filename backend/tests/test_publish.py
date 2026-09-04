"""Publish is the highest-risk part: it is the only thing that can break the
viewer for everybody at once."""

import json

from app.services import publish as publish_service
from app.storage import get_storage

from .helpers import build_show


def test_publish_produces_a_catalogue_and_records_the_run(client, admin):
    build_show(client, admin, "mango")
    r = client.post("/admin/catalog/publish", headers=admin)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "success"
    assert run["actor_email"] == "admin@peblo.tv"
    assert run["counts"]["shows"] == 1
    assert run["catalog_key"].startswith("catalog/runs/")
    assert run["finished_at"]

    catalog = client.get("/catalog").json()
    assert catalog["counts"]["shows"] == 1
    assert catalog["run_id"] == run["id"]


def test_language_variants_collapse_into_one_entry(client, admin):
    build_show(client, admin, "mango", languages=("en", "hi"))
    client.post("/admin/catalog/publish", headers=admin)
    show = client.get("/catalog/shows/mango").json()
    season = show["seasons"][0]
    assert len(season["episodes"]) == 1, "two language rows must collapse to one entry"
    entry = season["episodes"][0]
    assert [lang["code"] for lang in entry["languages"]] == ["en", "hi"]
    assert set(entry["variants"]) == {"en", "hi"}
    assert [lang["code"] for lang in show["languages"]] == ["en", "hi"]


def test_season_zero_is_trailers_not_a_season(client, admin):
    build_show(client, admin, "mango", with_trailer=True)
    client.post("/admin/catalog/publish", headers=admin)
    show = client.get("/catalog/shows/mango").json()
    assert [s["season_number"] for s in show["seasons"]] == [1]
    assert len(show["trailers"]) == 1
    assert show["trailers"][0]["title"] == "Trailer"


def test_only_published_content_appears(client, admin):
    build_show(client, admin, "mango")
    build_show(client, admin, "hidden", publish_show=False)
    client.post("/admin/catalog/publish", headers=admin)
    slugs = {s["slug"] for s in client.get("/catalog").json()["shows"]}
    assert slugs == {"mango"}


def test_publish_is_atomic_the_pointer_flips_only_at_the_end(client, admin, monkeypatch):
    """Simulate the process dying mid-publish: the live catalogue must be
    untouched, and the run recorded as failed."""
    build_show(client, admin, "mango")
    client.post("/admin/catalog/publish", headers=admin)
    good = client.get("/catalog").json()
    good_key = get_storage().get_pointer("catalog/current")

    build_show(client, admin, "second")

    real_put = get_storage().put

    def explode(key, data, content_type):
        if key.startswith("catalog/runs/"):
            raise OSError("disk went away halfway through the write")
        return real_put(key, data, content_type)

    monkeypatch.setattr(get_storage(), "put", explode)
    try:
        client.post("/admin/catalog/publish", headers=admin)
    except OSError:
        pass
    monkeypatch.undo()

    # The pointer never moved, so a reader still sees the whole previous catalogue.
    assert get_storage().get_pointer("catalog/current") == good_key
    from app.services import catalog_read
    catalog_read.invalidate()
    assert client.get("/catalog").json()["counts"] == good["counts"]

    runs = client.get("/admin/catalog/runs", headers=admin).json()
    assert runs[0]["status"] == "failed"
    assert "disk went away" in runs[0]["error"]


def test_readers_never_see_a_half_written_file(client, admin):
    """Run files are immutable and written under a run-scoped key; the live
    key is never opened for writing."""
    build_show(client, admin, "mango")
    r1 = client.post("/admin/catalog/publish", headers=admin).json()
    build_show(client, admin, "second")
    r2 = client.post("/admin/catalog/publish", headers=admin).json()
    assert r1["catalog_key"] != r2["catalog_key"]
    storage = get_storage()
    # The first run's file still exists, unmodified — that is what rollback uses.
    old = json.loads(storage.get(r1["catalog_key"]))
    assert old["counts"]["shows"] == 1


def test_publish_is_idempotent(client, admin):
    build_show(client, admin, "mango")
    first = client.post("/admin/catalog/publish", headers=admin).json()
    second = client.post("/admin/catalog/publish", headers=admin).json()
    assert second["status"] == "no_changes"
    assert second["catalog_key"] == first["catalog_key"]
    assert second["checksum"] == first["checksum"]


def test_publish_is_blocked_by_validation_and_the_attempt_is_recorded(client, admin):
    show_id, seasons = build_show(client, admin, "mango")
    # Break it the way an editor would: publish an episode, then remove the runtime.
    from app.db import SessionLocal
    from app.models import Episode, Season
    with SessionLocal() as db:
        season_id = db.query(Season).filter(Season.show_id == show_id,
                                            Season.season_number == 1).one().id
        ep = db.query(Episode).filter(Episode.season_id == season_id).first()
        ep.duration_seconds = None
        db.commit()

    r = client.post("/admin/catalog/publish", headers=admin)
    assert r.status_code == 409
    assert "must be fixed" in r.json()["detail"]["message"]
    assert client.get("/admin/catalog/runs", headers=admin).json()[0]["status"] == "blocked"


def test_rollback_restores_a_previous_run(client, admin):
    build_show(client, admin, "mango")
    first = client.post("/admin/catalog/publish", headers=admin).json()
    build_show(client, admin, "second")
    client.post("/admin/catalog/publish", headers=admin)
    assert client.get("/catalog").json()["counts"]["shows"] == 2

    r = client.post(f"/admin/catalog/rollback/{first['id']}", headers=admin)
    assert r.status_code == 200
    assert client.get("/catalog").json()["counts"]["shows"] == 1


def test_stale_run_is_swept_and_the_pointer_is_untouched(client, admin, db):
    from datetime import UTC, datetime, timedelta

    from app.models import PublishRun

    build_show(client, admin, "mango")
    client.post("/admin/catalog/publish", headers=admin)
    key_before = get_storage().get_pointer("catalog/current")

    db.add(PublishRun(actor_email="admin@peblo.tv", status="running",
                      started_at=datetime.now(UTC) - timedelta(hours=2)))
    db.commit()

    assert publish_service.sweep_stale_runs(db) == 1
    assert get_storage().get_pointer("catalog/current") == key_before
