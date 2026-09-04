from fastapi import APIRouter, HTTPException, Query, Response

from ..services import catalog_read
from ..storage import get_storage

router = APIRouter(tags=["viewer"])

EMPTY = {"schema_version": 1, "hero": None, "sections": [], "shows": [],
         "counts": {"shows": 0, "sections": 0, "episodes": 0},
         "message": "Nothing has been published yet."}


def _snapshot():
    doc = catalog_read.snapshot(get_storage())
    if doc is None:
        return None
    return doc


@router.get("/catalog")
def catalog(response: Response):
    """What the viewer reads. Never touches the content tables."""
    doc = _snapshot()
    if doc is None:
        response.headers["Cache-Control"] = "no-store"
        return EMPTY
    tag = catalog_read.etag()
    if tag:
        response.headers["ETag"] = tag
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=600"
    return catalog_read.public_document(doc)


@router.get("/catalog/search")
def search(
    q: str = "",
    category: str | None = None,
    language: str | None = None,
    section: str | None = Query(None),
):
    doc = _snapshot()
    if doc is None:
        return {"query": {"q": q, "category": category, "language": language, "section": section},
                "count": 0, "results": []}
    return catalog_read.search(doc, q=q, category=category, language=language, section=section)


@router.get("/catalog/shows/{slug}")
def show_detail(slug: str):
    doc = _snapshot()
    if doc is None:
        raise HTTPException(404, "Nothing has been published yet.")
    for show in doc["shows"]:
        if show["slug"] == slug:
            return catalog_read.strip_internal(show)
    raise HTTPException(404, "We couldn't find that show in the published catalogue.")
