"""Initial migration

Revision ID: 001
Revises:
Create Date: 2025-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Create regions table
    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.Geometry(geometry_type="POLYGON", srid=4326),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False, default="custom", index=True),
        sa.Column("country", sa.String(100), nullable=True, index=True),
        sa.Column("state_province", sa.String(100), nullable=True),
        sa.Column("category", sa.String(50), nullable=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create observations table
    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "region_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("regions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("metric", sa.String(50), nullable=False, index=True),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("raster_path", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )

    # Create analysis_results table
    op.create_table(
        "analysis_results",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "region_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("regions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("analysis_type", sa.String(50), nullable=False, index=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("results", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
    )

    # Create spatial index on regions geometry
    op.create_index(
        "idx_regions_geometry",
        "regions",
        ["geometry"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("idx_regions_geometry", table_name="regions")
    op.drop_table("api_keys")
    op.drop_table("analysis_results")
    op.drop_table("observations")
    op.drop_table("regions")
