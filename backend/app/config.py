from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Peblo TV Mini API"
    environment: str = "local"

    database_url: str = "postgresql+psycopg://peblo:peblo@db:5432/peblo"

    # Auth
    jwt_secret: str = "dev-only-not-a-real-secret"
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 720
    seed_admin_email: str = "admin@peblo.tv"
    seed_admin_password: str = "peblo-admin"
    seed_editor_email: str = "editor@peblo.tv"
    seed_editor_password: str = "peblo-editor"

    # Storage
    storage_backend: str = "local"  # local | r2
    storage_local_root: str = "/data/storage"
    storage_public_base_url: str = "http://localhost:8000/media"

    r2_endpoint_url: str = ""
    r2_bucket: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_public_base_url: str = ""

    # Content
    reference_path: str = str(REPO_ROOT / "data" / "reference.json")
    seed_path: str = str(REPO_ROOT / "data" / "seed_shows.json")
    seed_assets_dir: str = str(REPO_ROOT / "assets")
    auto_seed: bool = True
    auto_publish_on_seed: bool = True

    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
