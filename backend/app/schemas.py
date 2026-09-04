from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .reference import categories, languages, sections

STATUSES = ("draft", "published", "archived")


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    email: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    role: str


class ShowIn(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = ""
    category: str | None = None
    section: str | None = None
    status: str = "draft"
    featured: bool = False
    sort_weight: int = 100

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in STATUSES:
            raise ValueError(f"Status must be one of {', '.join(STATUSES)}.")
        return v

    @field_validator("category")
    @classmethod
    def _category(cls, v):
        if v and v not in categories():
            raise ValueError(f"“{v}” isn't an approved category. Pick one of: {', '.join(categories())}.")
        return v

    @field_validator("section")
    @classmethod
    def _section(cls, v):
        if v and v not in sections():
            raise ValueError(f"“{v}” isn't a section we ship. Pick one of: {', '.join(sections())}.")
        return v

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not all(c.isalnum() or c == "-" for c in cleaned):
            raise ValueError("The URL slug can only contain lowercase letters, numbers and hyphens.")
        return cleaned


class ShowUpdate(ShowIn):
    slug: str | None = None
    title: str | None = None


class SeasonIn(BaseModel):
    season_number: int = Field(ge=0)
    title: str = ""


class SeasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    season_number: int
    title: str


class EpisodeIn(BaseModel):
    season_id: str
    episode_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=250)
    synopsis: str = ""
    duration_seconds: int | None = None
    language: str
    content_group: str | None = None
    status: str = "draft"
    release_date: date | None = None

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in languages():
            raise ValueError(f"“{v}” isn't a language we ship. Pick one of: {', '.join(languages())}.")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in STATUSES:
            raise ValueError(f"Status must be one of {', '.join(STATUSES)}.")
        return v

    @field_validator("duration_seconds")
    @classmethod
    def _duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Runtime must be longer than zero. Enter the episode's real length.")
        return v


class EpisodeUpdate(EpisodeIn):
    season_id: str | None = None
    episode_number: int | None = None
    title: str | None = None
    language: str | None = None


class ArtworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    width: int
    height: int
    bytes: int
    mime_type: str
    url: str = ""


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    season_id: str
    episode_number: int
    title: str
    synopsis: str
    duration_seconds: int | None
    language: str
    content_group: str | None
    status: str
    release_date: date | None
    artwork: list[ArtworkOut] = []


class ShowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    title: str
    synopsis: str
    category: str | None
    section: str | None
    status: str
    featured: bool
    sort_weight: int
    updated_at: datetime
    seasons: list[SeasonOut] = []
    artwork: list[ArtworkOut] = []
    episode_count: int = 0
    languages: list[str] = []


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int


class PublishRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_email: str | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    counts: dict
    catalog_key: str | None
    checksum: str | None
    error: str | None
