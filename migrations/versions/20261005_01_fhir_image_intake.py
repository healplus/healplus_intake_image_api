"""Create FHIR image intake resources."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261005_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tables for Bundle, Media, Coding, and Task resources."""
    op.create_table(
        "fhir_bundles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("identifier_system", sa.String(length=255)),
        sa.Column("identifier_value", sa.String(length=255)),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
        sa.Column("resource_json", postgresql.JSONB(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "media",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("full_url", sa.String(length=512)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subject_reference", sa.String(length=512), nullable=False),
        sa.Column("encounter_reference", sa.String(length=512)),
        sa.Column("created_date_time", sa.DateTime(timezone=True)),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("content_data", sa.Text(), nullable=False),
        sa.Column("resource_json", postgresql.JSONB(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["fhir_bundles.id"]),
    )
    op.create_index("ix_media_bundle_id", "media", ["bundle_id"])
    op.create_table(
        "media_type_codings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("media_id", sa.String(length=64), nullable=False),
        sa.Column("system", sa.String(length=255)),
        sa.Column("code", sa.String(length=255)),
        sa.Column("display", sa.String(length=255)),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"]),
    )
    op.create_index("ix_media_type_codings_media_id", "media_type_codings", ["media_id"])
    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subject_reference", sa.String(length=512)),
        sa.Column("resource_json", postgresql.JSONB(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("authored_on", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["fhir_bundles.id"]),
    )
    op.create_index("ix_analysis_tasks_status", "analysis_tasks", ["status"])


def downgrade() -> None:
    """Remove FHIR image intake tables."""
    op.drop_index("ix_analysis_tasks_status", table_name="analysis_tasks")
    op.drop_table("analysis_tasks")
    op.drop_index("ix_media_type_codings_media_id", table_name="media_type_codings")
    op.drop_table("media_type_codings")
    op.drop_index("ix_media_bundle_id", table_name="media")
    op.drop_table("media")
    op.drop_table("fhir_bundles")
