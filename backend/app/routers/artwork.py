from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import require_editor
from ..db import get_db
from ..models import Artwork, AuditLog, Episode, Show, User
from ..reference import artwork_specs
from ..services import artwork as art_service
from ..storage import get_storage

router = APIRouter(prefix="/admin/artwork", tags=["admin: artwork"])

OWNER_MODELS = {"show": Show, "episode": Episode}
# A poster/banner belongs to a show; a thumbnail belongs to an episode.
ALLOWED_KINDS = {"show": {"poster", "banner"}, "episode": {"thumbnail"}}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # hard stop before we even decode


@router.get("/specs")
def specs(_: User = Depends(require_editor)):
    return artwork_specs()


@router.post("/{owner_type}/{owner_id}/{kind}", status_code=201)
async def upload(owner_type: str, owner_id: str, kind: str, file: UploadFile = File(...),
                 db: Session = Depends(get_db), user: User = Depends(require_editor)):
    if owner_type not in OWNER_MODELS:
        raise HTTPException(404, "Artwork can only be attached to a show or an episode.")
    if kind not in ALLOWED_KINDS[owner_type]:
        raise HTTPException(
            422,
            f"A {owner_type} doesn't have a {kind} slot. "
            f"It has: {', '.join(sorted(ALLOWED_KINDS[owner_type]))}.",
        )
    owner = db.get(OWNER_MODELS[owner_type], owner_id)
    if not owner:
        raise HTTPException(404, f"We couldn't find that {owner_type}.")

    data = await file.read()
    if not data:
        raise HTTPException(422, "That file was empty. Try exporting it again.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is far too large to process. Export it under 10 MB first.")

    try:
        image = art_service.inspect(data)
        art_service.validate(kind, image)
    except art_service.ArtworkRejected as rejected:
        # 422 with a list an editor can act on, one entry per problem.
        raise HTTPException(422, {"message": "We can't use this image yet.",
                                  "problems": rejected.problems}) from None

    storage = get_storage()
    key = art_service.storage_key(owner_type, owner_id, kind, image)
    storage.put(key, data, image.mime)

    existing = db.query(Artwork).filter(
        Artwork.owner_type == owner_type, Artwork.owner_id == owner_id, Artwork.kind == kind
    ).first()
    if existing:
        old_key = existing.storage_key
        existing.storage_key = key
        existing.mime_type = image.mime
        existing.width, existing.height = image.width, image.height
        existing.bytes, existing.checksum = image.bytes, image.checksum
        existing.uploaded_by = user.id
        record = existing
        if old_key != key:
            storage.delete(old_key)
    else:
        record = Artwork(owner_type=owner_type, owner_id=owner_id, kind=kind, storage_key=key,
                         mime_type=image.mime, width=image.width, height=image.height,
                         bytes=image.bytes, checksum=image.checksum, uploaded_by=user.id)
        db.add(record)
    db.add(AuditLog(actor_email=user.email, entity="artwork", entity_id=f"{owner_type}:{owner_id}",
                    action=f"upload:{kind}", detail={"bytes": image.bytes,
                                                     "size": f"{image.width}x{image.height}"}))
    db.commit()
    db.refresh(record)
    return {"id": record.id, "kind": kind, "url": storage.public_url(key), "width": image.width,
            "height": image.height, "bytes": image.bytes, "mime_type": image.mime}


@router.delete("/{artwork_id}", status_code=204)
def delete(artwork_id: str, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    record = db.get(Artwork, artwork_id)
    if not record:
        raise HTTPException(404, "That image is already gone.")
    get_storage().delete(record.storage_key)
    db.add(AuditLog(actor_email=user.email, entity="artwork", entity_id=record.id, action="delete"))
    db.delete(record)
    db.commit()
