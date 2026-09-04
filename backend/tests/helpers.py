from .conftest import image_bytes


def build_show(client, headers, slug="mango", *, section="New on Peblo", category="Comedy",
               languages=("en", "hi"), publish_show=True, with_trailer=True):
    """A complete, publishable show: artwork, one season, one grouped episode."""
    r = client.post("/admin/shows", json={
        "slug": slug, "title": slug.replace("-", " ").title(), "synopsis": "A show.",
        "category": category, "section": section, "status": "draft"}, headers=headers)
    show = r.json()
    show_id = show["id"]
    for kind, size in (("poster", (600, 900)), ("banner", (1280, 720))):
        client.post(f"/admin/artwork/show/{show_id}/{kind}",
                    files={"file": (f"{kind}.jpg", image_bytes(*size), "image/jpeg")},
                    headers=headers)
    seasons = {s["season_number"]: s["id"] for s in show["seasons"]}

    def add_ep(season_number, number, group, language, title, status="published", duration=600):
        r = client.post("/admin/episodes", json={
            "season_id": seasons[season_number], "episode_number": number, "title": title,
            "duration_seconds": duration, "language": language, "content_group": group,
            "status": "draft"}, headers=headers)
        assert r.status_code == 201, r.text
        ep_id = r.json()["id"]
        client.post(f"/admin/artwork/episode/{ep_id}/thumbnail",
                    files={"file": ("t.jpg", image_bytes(640, 360), "image/jpeg")}, headers=headers)
        if status == "published":
            r = client.patch(f"/admin/episodes/{ep_id}", json={"status": "published"},
                             headers=headers)
            assert r.status_code == 200, r.text
        return ep_id

    for language in languages:
        add_ep(1, 1, f"{slug}-s1e1", language, "The First Loud Morning")
    if with_trailer:
        add_ep(0, 1, f"{slug}-trailer", "en", "Trailer", duration=75)

    if publish_show:
        client.patch(f"/admin/shows/{show_id}", json={"status": "published"}, headers=headers)
    return show_id, seasons
