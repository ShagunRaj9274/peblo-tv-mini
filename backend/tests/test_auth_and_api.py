"""Roles have to be enforced, not declared. And the viewer must not be able to
reach anything under /admin."""

from .helpers import build_show


def test_editor_cannot_publish(client, editor):
    build_show(client, editor, "mango")
    r = client.post("/admin/catalog/publish", headers=editor)
    assert r.status_code == 403
    assert "admin role" in r.json()["detail"]


def test_editor_can_crud(client, editor):
    r = client.post("/admin/shows", json={"slug": "new-show", "title": "New Show",
                                          "category": "Comedy"}, headers=editor)
    assert r.status_code == 201


def test_admin_can_do_both(client, admin):
    build_show(client, admin, "mango")
    assert client.post("/admin/catalog/publish", headers=admin).status_code == 200


def test_anonymous_gets_401_on_admin_routes(client):
    for method, path in [("get", "/admin/shows"), ("get", "/admin/validation-report"),
                         ("post", "/admin/catalog/publish")]:
        r = getattr(client, method)(path)
        assert r.status_code == 401, path


def test_viewer_endpoints_need_no_auth(client, admin):
    build_show(client, admin, "mango")
    client.post("/admin/catalog/publish", headers=admin)
    assert client.get("/catalog").status_code == 200
    assert client.get("/catalog/search?q=mango").status_code == 200


def test_bad_credentials_are_rejected(client):
    assert client.post("/auth/login", json={"email": "admin@peblo.tv",
                                            "password": "wrong"}).status_code == 401


def test_duplicate_content_group_and_language_is_rejected(client, editor):
    show_id, _ = build_show(client, editor, "mango", languages=("en",), publish_show=False)
    show = client.get(f"/admin/shows/{show_id}", headers=editor).json()
    season = next(s for s in show["seasons"] if s["season_number"] == 1)
    r = client.post("/admin/episodes", json={
        "season_id": season["id"], "episode_number": 1, "title": "Duplicate",
        "duration_seconds": 600, "language": "en", "content_group": "mango-s1e1"}, headers=editor)
    assert r.status_code == 409
    assert "one episode per language" in r.json()["detail"]


def test_publishing_a_show_without_a_section_is_refused(client, editor):
    r = client.post("/admin/shows", json={"slug": "no-section", "title": "No Section",
                                          "category": "Comedy", "status": "published"},
                    headers=editor)
    assert r.status_code == 422
    assert "needs a section" in r.json()["detail"]


def test_episode_cannot_be_published_without_a_duration(client, editor):
    show_id, _ = build_show(client, editor, "mango", publish_show=False)
    show = client.get(f"/admin/shows/{show_id}", headers=editor).json()
    season = next(s for s in show["seasons"] if s["season_number"] == 1)
    r = client.post("/admin/episodes", json={
        "season_id": season["id"], "episode_number": 9, "title": "No runtime",
        "language": "en", "content_group": "mango-s1e9", "status": "published"}, headers=editor)
    assert r.status_code == 422
    assert "runtime" in r.json()["detail"]


def test_unknown_category_is_refused_with_the_allowed_list(client, editor):
    r = client.post("/admin/shows", json={"slug": "x", "title": "X", "category": "Edutainment"},
                    headers=editor)
    assert r.status_code == 422
    assert "Adventure" in str(r.json()["detail"])
