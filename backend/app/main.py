import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import SessionLocal, engine
from .models import Base
from .routers import admin_content, artwork, auth_router, catalog_router, health, publish_router
from .services import publish as publish_service

log = logging.getLogger("peblo")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic owns the schema in docker-compose (see backend/entrypoint.sh).
    # create_all is a safety net for `pytest` and bare `uvicorn app.main:app`.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        swept = publish_service.sweep_stale_runs(db)
        if swept:
            log.warning("Marked %s interrupted publish run(s) as failed. Live catalogue untouched.", swept)
        if settings.auto_seed:
            from . import seed

            result = seed.run(db)
            if result.get("notes"):
                log.info("Seed import: %s rows, %s notes", result.get("rows"), len(result["notes"]))
                for note in result["notes"][:40]:
                    log.info("  seed: %s", note)
            # A first publish so a fresh `docker-compose up` shows a populated viewer
            # rather than an empty state that looks like a bug.
            if settings.auto_publish_on_seed and not result.get("skipped"):
                from .models import User
                from .storage import get_storage

                actor = db.query(User).filter(User.role == "admin").first()
                if actor:
                    try:
                        run = publish_service.publish(db, get_storage(), actor)
                        log.info("Initial publish: %s %s", run.status, run.counts)
                    except publish_service.PublishBlocked as blocked:
                        log.warning("Initial publish blocked: %s", blocked.report["summary"])
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    description="CMS API, publish job, and the read-only catalogue the viewer consumes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(admin_content.router)
app.include_router(artwork.router)
app.include_router(publish_router.router)

# Local-disk storage is served by the API so the compose stack needs no extra
# service. With STORAGE_BACKEND=r2 this mount is unused: images come from the CDN.
if settings.storage_backend == "local":
    root = Path(settings.storage_local_root)
    root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(root)), name="media")


@app.get("/", include_in_schema=False)
def root():
    return {"service": settings.app_name, "docs": "/docs", "catalog": "/catalog",
            "health": "/health/ready"}
