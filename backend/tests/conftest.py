import os
import tempfile

import pytest

TMP = tempfile.mkdtemp(prefix="peblo-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TMP}/test.db",
    "STORAGE_LOCAL_ROOT": f"{TMP}/storage",
    "STORAGE_PUBLIC_BASE_URL": "http://testserver/media",
    "AUTO_SEED": "false",
    "JWT_SECRET": "test-secret",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed_users  # noqa: E402
from app.services import catalog_read  # noqa: E402
from app.storage import get_storage  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    storage = get_storage()
    storage.wipe()
    catalog_read.invalidate()
    with SessionLocal() as db:
        seed_users(db)
    with TestClient(app) as c:
        yield c


def token(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return token(client, "admin@peblo.tv", "peblo-admin")


@pytest.fixture()
def editor(client):
    return token(client, "editor@peblo.tv", "peblo-editor")


@pytest.fixture()
def db():
    with SessionLocal() as session:
        yield session


def image_bytes(w: int, h: int, quality: int = 80, fmt: str = "JPEG", noisy: bool = False) -> bytes:
    import io
    import random

    from PIL import Image

    img = Image.new("RGB", (w, h), (40, 60, 90))
    if noisy:
        px = img.load()
        random.seed(1)
        for y in range(h):
            for x in range(w):
                px[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()
