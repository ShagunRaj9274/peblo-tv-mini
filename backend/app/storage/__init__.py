from functools import lru_cache

from ..config import settings
from .base import ObjectStorage
from .local import LocalDiskStorage
from .r2 import R2Storage

__all__ = ["ObjectStorage", "LocalDiskStorage", "R2Storage", "get_storage"]


@lru_cache
def get_storage() -> ObjectStorage:
    if settings.storage_backend == "r2":
        return R2Storage(
            endpoint_url=settings.r2_endpoint_url,
            bucket=settings.r2_bucket,
            access_key=settings.r2_access_key_id,
            secret_key=settings.r2_secret_access_key,
            public_base_url=settings.r2_public_base_url or settings.storage_public_base_url,
        )
    return LocalDiskStorage(settings.storage_local_root, settings.storage_public_base_url)
