from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    """Everything the app is allowed to know about where bytes live.

    Two rules make the Cloudflare R2 swap a one-class change:
      * nothing outside this package builds a filesystem path or an S3 key by hand;
      * "which catalogue is live" is a *pointer object*, never a mutated file.
        Both backends implement the pointer as a single small write, which is
        atomic on POSIX (os.replace) and atomic on S3/R2 (a PUT is all-or-nothing).
    """

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Write an immutable object. Returns the key."""

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def public_url(self, key: str) -> str:
        """A URL a browser can fetch. Local: served by the API. R2: CDN domain."""

    @abstractmethod
    def set_pointer(self, name: str, key: str) -> None:
        """Atomically point `name` at `key`. This is the publish swap."""

    @abstractmethod
    def get_pointer(self, name: str) -> str | None: ...
