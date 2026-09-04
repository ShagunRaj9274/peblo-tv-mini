import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (CheckConstraint("role in ('editor','admin')", name="ck_users_role"),)


class Show(Base):
    __tablename__ = "shows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String(60))
    section: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_weight: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    seasons: Mapped[list["Season"]] = relationship(
        back_populates="show", cascade="all, delete-orphan", order_by="Season.season_number"
    )

    __table_args__ = (
        CheckConstraint("status in ('draft','published','archived')", name="ck_shows_status"),
        # The publish job and the CMS list both filter on (status, section); the
        # composite index covers "everything publishable in this section" directly.
        Index("ix_shows_status_section", "status", "section"),
        Index("ix_shows_title", "title"),
    )


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    show_id: Mapped[str] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="")

    show: Mapped[Show] = relationship(back_populates="seasons")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="season", cascade="all, delete-orphan", order_by="Episode.episode_number"
    )

    __table_args__ = (
        UniqueConstraint("show_id", "season_number", name="uq_seasons_show_number"),
        CheckConstraint("season_number >= 0", name="ck_seasons_number_nonneg"),
    )


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    season_id: Mapped[str] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(12), nullable=False)
    content_group: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date)
    source_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    season: Mapped[Season] = relationship(back_populates="episodes")

    __table_args__ = (
        # The brief's hard rule. Enforced in the database, not just in the service layer.
        UniqueConstraint("content_group", "language", name="uq_episodes_group_language"),
        CheckConstraint("status in ('draft','published','archived')", name="ck_episodes_status"),
        CheckConstraint(
            "duration_seconds is null or duration_seconds > 0", name="ck_episodes_duration_positive"
        ),
        Index("ix_episodes_season_number", "season_id", "episode_number"),
        # Grouping variants at publish time is a scan by content_group.
        Index("ix_episodes_content_group", "content_group"),
        Index("ix_episodes_status", "status"),
    )


class Artwork(Base):
    __tablename__ = "artwork"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)  # show | episode
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # poster | banner | thumbnail
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(60), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (
        # One current image per slot per owner: uploading again replaces the slot.
        UniqueConstraint("owner_type", "owner_id", "kind", name="uq_artwork_owner_kind"),
        CheckConstraint("owner_type in ('show','episode')", name="ck_artwork_owner_type"),
        CheckConstraint("kind in ('poster','banner','thumbnail')", name="ck_artwork_kind"),
    )


class PublishRun(Base):
    __tablename__ = "publish_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    actor_email: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    catalog_key: Mapped[str | None] = mapped_column(String(400))
    checksum: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('running','success','no_changes','failed','blocked','dry_run')",
            name="ck_publish_runs_status",
        ),
        Index("ix_publish_runs_started_at", "started_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (Index("ix_audit_entity", "entity", "entity_id"),)
