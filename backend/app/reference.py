import json
from functools import lru_cache
from pathlib import Path

from .config import settings


@lru_cache
def reference() -> dict:
    path = Path(settings.reference_path)
    if not path.exists():  # pragma: no cover
        raise RuntimeError(f"reference.json not found at {path}")
    return json.loads(path.read_text())


def sections() -> list[str]:
    return reference()["sections"]


def categories() -> list[str]:
    return reference()["categories"]


def languages() -> list[str]:
    return reference()["languages"]


def artwork_specs() -> dict:
    return reference()["artwork"]


def tolerance() -> dict:
    return reference().get("artwork_tolerance", {})


TRAILER_SEASON = 0


def section_order(name: str | None) -> int:
    """Sections render in reference.json order — that is the deterministic ordering."""
    try:
        return sections().index(name)
    except ValueError:
        return len(sections()) + 1
