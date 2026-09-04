"""Read side: serve the published catalogue, and search it.

The viewer never touches Postgres. It reads a snapshot that this module caches
in process, keyed by the pointer value. Because run keys are immutable, a cached
snapshot can never be stale in a dangerous way: either the pointer still names
the key we cached, or it names a new one and we reload.

Search is a linear scan over that snapshot with a pre-flattened `search_blob`.
See the README for the honest answer on where that stops working.
"""

import threading
import unicodedata

from ..storage import ObjectStorage
from . import publish

_lock = threading.Lock()
_cache: dict = {"key": None, "document": None, "etag": None}


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").casefold().strip()


def snapshot(storage: ObjectStorage, force: bool = False) -> dict | None:
    key = publish.current_key(storage)
    if key is None:
        return None
    with _lock:
        if force or _cache["key"] != key:
            if not storage.exists(key):
                return None
            document = publish.load_current(storage)
            _cache.update({"key": key, "document": document, "etag": f'W/"{key.split("/")[-1]}"'})
        return _cache["document"]


def etag() -> str | None:
    return _cache["etag"]


def invalidate() -> None:
    with _lock:
        _cache.update({"key": None, "document": None, "etag": None})


def _matches(show: dict, q: str, category: str | None, language: str | None,
             section: str | None) -> bool:
    if category and show.get("category") != category:
        return False
    if section and show.get("section") != section:
        return False
    if language and language not in {lang["code"] for lang in show.get("languages", [])}:
        return False
    if q:
        blob = show.get("search_blob") or ""
        return all(term in blob for term in q.split())
    return True


def search(document: dict, q: str = "", category: str | None = None, language: str | None = None,
           section: str | None = None) -> dict:
    """q matches show title, episode titles and category. Filters compose (AND)."""
    q = _normalise(q)
    hits = [s for s in document["shows"] if _matches(s, q, category, language, section)]

    def rank(show: dict) -> tuple:
        if not q:
            return (0, show["title"])
        title = _normalise(show["title"])
        # exact title < prefix < category hit < episode-only hit
        if title == q:
            tier = 0
        elif title.startswith(q):
            tier = 1
        elif q in title:
            tier = 2
        elif q in _normalise(show.get("category") or ""):
            tier = 3
        else:
            tier = 4
        return (tier, show["title"])

    hits.sort(key=rank)
    return {
        "query": {"q": q, "category": category, "language": language, "section": section},
        "count": len(hits),
        "results": [strip_internal(s) for s in hits],
    }


def strip_internal(show: dict) -> dict:
    return {k: v for k, v in show.items() if k != "search_blob"}


def public_document(document: dict) -> dict:
    return {**document, "shows": [strip_internal(s) for s in document["shows"]]}
