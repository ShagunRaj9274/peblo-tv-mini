"""Artwork rules are the first thing an editor hits, and the easiest thing to
accidentally leave client-side. These tests assert the *server* rejects."""

from .conftest import image_bytes


def make_show(client, headers, slug="test-show"):
    r = client.post("/admin/shows", json={"slug": slug, "title": "Test Show",
                                          "category": "Comedy", "section": "New on Peblo"},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, headers, owner_type, owner_id, kind, data, name="a.jpg"):
    return client.post(f"/admin/artwork/{owner_type}/{owner_id}/{kind}",
                       files={"file": (name, data, "image/jpeg")}, headers=headers)


def test_correct_poster_is_accepted(client, editor):
    show = make_show(client, editor)
    r = upload(client, editor, "show", show, "poster", image_bytes(600, 900))
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["width"], body["height"]) == (600, 900)
    assert body["url"].endswith(".jpg")


def test_wrong_aspect_ratio_is_rejected_with_a_readable_message(client, editor):
    show = make_show(client, editor)
    r = upload(client, editor, "show", show, "poster", image_bytes(900, 900))
    assert r.status_code == 422
    problems = r.json()["detail"]["problems"]
    codes = {p["code"] for p in problems}
    assert "bad_aspect_ratio" in codes
    message = next(p["message"] for p in problems if p["code"] == "bad_aspect_ratio")
    assert "2:3" in message and "900×900" in message


def test_file_over_200kb_is_rejected(client, editor):
    show = make_show(client, editor)
    heavy = image_bytes(1280, 720, quality=100, noisy=True)
    assert len(heavy) > 204800
    r = upload(client, editor, "show", show, "banner", heavy)
    assert r.status_code == 422
    assert "too_heavy" in {p["code"] for p in r.json()["detail"]["problems"]}


def test_undersized_thumbnail_is_rejected(client, editor):
    show = make_show(client, editor)
    ep = _episode(client, editor, show)
    r = upload(client, editor, "episode", ep, "thumbnail", image_bytes(160, 90))
    assert r.status_code == 422
    assert "too_small" in {p["code"] for p in r.json()["detail"]["problems"]}


def test_all_three_slots_have_distinct_rules(client, editor):
    show = make_show(client, editor)
    # A valid banner is not a valid poster: the shape differs.
    assert upload(client, editor, "show", show, "banner", image_bytes(1280, 720)).status_code == 201
    assert upload(client, editor, "show", show, "poster", image_bytes(1280, 720)).status_code == 422


def test_reupload_replaces_the_slot_rather_than_stacking(client, editor):
    show = make_show(client, editor)
    first = upload(client, editor, "show", show, "poster", image_bytes(600, 900, quality=70)).json()
    second = upload(client, editor, "show", show, "poster", image_bytes(600, 900, quality=95)).json()
    assert first["id"] == second["id"]
    assert first["url"] != second["url"]


def test_non_image_upload_is_rejected(client, editor):
    show = make_show(client, editor)
    r = upload(client, editor, "show", show, "poster", b"this is not an image")
    assert r.status_code == 422
    assert r.json()["detail"]["problems"][0]["code"] == "not_an_image"


def _episode(client, headers, show_id):
    seasons = client.get(f"/admin/shows/{show_id}", headers=headers).json()["seasons"]
    season = next(s for s in seasons if s["season_number"] == 1)
    r = client.post("/admin/episodes", json={
        "season_id": season["id"], "episode_number": 1, "title": "Pilot",
        "duration_seconds": 600, "language": "en", "content_group": "test-s1e1"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]
