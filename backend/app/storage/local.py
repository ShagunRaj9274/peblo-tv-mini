import os
import shutil
import tempfile
from pathlib import Path

from .base import ObjectStorage


class LocalDiskStorage(ObjectStorage):
    def __init__(self, root: str, public_base_url: str):
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Refuse anything that would escape the root.
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError(f"illegal storage key: {key}")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(p, data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def set_pointer(self, name: str, key: str) -> None:
        self._atomic_write(
            self._path(f"{name}.pointer"),
            key.encode(),
        )

    def get_pointer(self, name: str) -> str | None:
        p = self._path(f"{name}.pointer")
        return p.read_text().strip() if p.exists() else None

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp = tempfile.mkstemp(
            dir=path.parent,
            suffix=".tmp",
        )

        try:
            # Write data to temporary file and flush it to disk.
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())

            # Atomically replace the destination file.
            os.replace(tmp, path)

            # POSIX systems can fsync the directory to ensure the rename
            # survives a power failure. Windows does not provide O_DIRECTORY,
            # so skip this optional step there.
            try:
                dir_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (AttributeError, OSError):
                pass

        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def wipe(self) -> None:
        # Test helper
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)