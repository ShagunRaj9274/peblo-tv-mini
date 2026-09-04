"""Server-side artwork validation.

Every rule here also exists in the CMS, but the CMS copy is only a courtesy —
this is the copy that decides. Error messages are written for a content editor:
what is wrong, what was expected, and what to do next. No mime strings, no
"validation failed on field artwork[0]".
"""

import hashlib
import io
from dataclasses import dataclass, field

from PIL import Image, UnidentifiedImageError

from ..reference import artwork_specs, tolerance

KIND_LABELS = {"poster": "Poster", "banner": "Banner", "thumbnail": "Thumbnail"}
EXT_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class ArtworkRejected(Exception):
    def __init__(self, problems: list[dict]):
        self.problems = problems
        super().__init__("; ".join(p["message"] for p in problems))


@dataclass
class InspectedImage:
    width: int
    height: int
    bytes: int
    mime: str
    checksum: str
    data: bytes = field(repr=False, default=b"")

    @property
    def extension(self) -> str:
        return EXT_BY_MIME.get(self.mime, "bin")


def _kb(n: int) -> str:
    return f"{n / 1024:.0f} KB"


def inspect(data: bytes) -> InspectedImage:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            fmt = (img.format or "").lower()
    except (UnidentifiedImageError, OSError) as exc:
        raise ArtworkRejected(
            [
                {
                    "code": "not_an_image",
                    "message": "That file isn't an image we can read. Upload a JPG, PNG or WebP "
                    "exported from your design tool.",
                }
            ]
        ) from exc
    mime = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(fmt, f"image/{fmt}")
    return InspectedImage(
        width=width,
        height=height,
        bytes=len(data),
        mime=mime,
        checksum=hashlib.sha256(data).hexdigest(),
        data=data,
    )


def validate(kind: str, image: InspectedImage) -> None:
    """Raise ArtworkRejected listing *every* problem, so the editor fixes the
    image once instead of re-uploading to discover the next complaint."""
    specs = artwork_specs()
    if kind not in specs:
        raise ArtworkRejected(
            [{"code": "unknown_slot", "message": f"'{kind}' isn't one of the artwork slots "
              f"({', '.join(specs)})."}]
        )

    spec = specs[kind]
    tol = tolerance()
    label = KIND_LABELS.get(kind, kind)
    tw, th = spec["target_width"], spec["target_height"]
    max_bytes = spec["max_bytes"]
    allowed_mimes = tol.get("allowed_mime_types", ["image/jpeg", "image/png", "image/webp"])
    ratio_tol = float(tol.get("aspect_ratio_tolerance", 0.02))
    dim_tol = float(tol.get("dimension_tolerance_pct", 0.10))

    problems: list[dict] = []

    if image.mime not in allowed_mimes:
        pretty = ", ".join(EXT_BY_MIME.get(m, m).upper() for m in allowed_mimes)
        problems.append(
            {
                "code": "bad_format",
                "message": f"{label} must be a {pretty} file. Re-export this one and try again.",
            }
        )

    target_ratio = tw / th
    actual_ratio = image.width / image.height if image.height else 0
    if target_ratio and abs(actual_ratio - target_ratio) / target_ratio > ratio_tol:
        problems.append(
            {
                "code": "bad_aspect_ratio",
                "message": f"{label} must be {spec['aspect_ratio']} (like {tw}×{th}). "
                f"This image is {image.width}×{image.height}, which is the wrong shape — "
                f"crop it rather than stretching it.",
                "expected": spec["aspect_ratio"],
                "actual": f"{image.width}×{image.height}",
            }
        )

    if image.width < tw * (1 - dim_tol) or image.height < th * (1 - dim_tol):
        problems.append(
            {
                "code": "too_small",
                "message": f"{label} is too small at {image.width}×{image.height}. It needs to be at "
                f"least {tw}×{th}, or it will look blurry on a TV. Export at the original size.",
                "expected": f"{tw}×{th}",
                "actual": f"{image.width}×{image.height}",
            }
        )
    elif image.width > tw * (1 + dim_tol) or image.height > th * (1 + dim_tol):
        problems.append(
            {
                "code": "too_large",
                "message": f"{label} is bigger than we serve. Resize to {tw}×{th} "
                f"(this one is {image.width}×{image.height}).",
                "expected": f"{tw}×{th}",
                "actual": f"{image.width}×{image.height}",
            }
        )

    if image.bytes > max_bytes:
        problems.append(
            {
                "code": "too_heavy",
                "message": f"{label} is {_kb(image.bytes)}. The limit is {_kb(max_bytes)} so it loads "
                f"quickly on a slow connection. Save it as a JPG at around 80% quality, or use "
                f"Squoosh, and upload again.",
                "expected": _kb(max_bytes),
                "actual": _kb(image.bytes),
            }
        )

    if problems:
        raise ArtworkRejected(problems)


def storage_key(owner_type: str, owner_id: str, kind: str, image: InspectedImage) -> str:
    # Content-addressed: re-uploading the same bytes is a no-op, and images are
    # immutable so they can be cached forever at the CDN edge.
    return f"artwork/{owner_type}/{owner_id}/{kind}-{image.checksum[:16]}.{image.extension}"
