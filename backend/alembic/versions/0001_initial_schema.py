"""initial schema: users, shows, seasons, episodes, artwork, publish runs, audit log

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role in ('editor','admin')", name="ck_users_role"),
    )

    op.create_table(
        "shows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("synopsis", sa.Text(), server_default=""),
        sa.Column("category", sa.String(60)),
        sa.Column("section", sa.String(80)),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status in ('draft','published','archived')", name="ck_shows_status"),
    )
    # Publish and the CMS list both ask "what is publishable in this section".
    op.create_index("ix_shows_status_section", "shows", ["status", "section"])
    op.create_index("ix_shows_title", "shows", ["title"])

    op.create_table(
        "seasons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("show_id", sa.String(36), sa.ForeignKey("shows.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), server_default=""),
        sa.UniqueConstraint("show_id", "season_number", name="uq_seasons_show_number"),
        sa.CheckConstraint("season_number >= 0", name="ck_seasons_number_nonneg"),
    )

    op.create_table(
        "episodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("season_id", sa.String(36), sa.ForeignKey("seasons.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("synopsis", sa.Text(), server_default=""),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("content_group", sa.String(160)),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("release_date", sa.Date()),
        sa.Column("source_ref", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # The brief's rule, enforced by the database rather than by hope.
        sa.UniqueConstraint("content_group", "language", name="uq_episodes_group_language"),
        sa.CheckConstraint("status in ('draft','published','archived')", name="ck_episodes_status"),
        sa.CheckConstraint("duration_seconds is null or duration_seconds > 0",
                           name="ck_episodes_duration_positive"),
    )
    op.create_index("ix_episodes_season_number", "episodes", ["season_id", "episode_number"])
    op.create_index("ix_episodes_content_group", "episodes", ["content_group"])
    op.create_index("ix_episodes_status", "episodes", ["status"])

    op.create_table(
        "artwork",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_type", sa.String(16), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("storage_key", sa.String(400), nullable=False),
        sa.Column("mime_type", sa.String(60), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_type", "owner_id", "kind", name="uq_artwork_owner_kind"),
        sa.CheckConstraint("owner_type in ('show','episode')", name="ck_artwork_owner_type"),
        sa.CheckConstraint("kind in ('poster','banner','thumbnail')", name="ck_artwork_kind"),
    )

    op.create_table(
        "publish_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("actor_email", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("counts", sa.JSON(), server_default="{}"),
        sa.Column("catalog_key", sa.String(400)),
        sa.Column("checksum", sa.String(64)),
        sa.Column("error", sa.Text()),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint(
            "status in ('running','success','no_changes','failed','blocked','dry_run')",
            name="ck_publish_runs_status",
        ),
    )
    op.create_index("ix_publish_runs_started_at", "publish_runs", ["started_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_email", sa.String(255)),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("detail", sa.JSON(), server_default="{}"),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_entity", "audit_log", ["entity", "entity_id"])


def downgrade() -> None:
    for table in ("audit_log", "publish_runs", "artwork", "episodes", "seasons", "shows", "users"):
        op.drop_table(table)
