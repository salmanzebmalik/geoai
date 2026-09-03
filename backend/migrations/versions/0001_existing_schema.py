"""Baseline existing GeoAI schema.

Revision ID: 0001_existing_schema
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_existing_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "segmentation_queries",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "min_lat",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "max_lat",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "min_lon",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "max_lon",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "image_url",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "image_width",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "image_height",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "prediction_result",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_created_at",
        "segmentation_queries",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_created_at",
        table_name="segmentation_queries",
    )

    op.drop_table("segmentation_queries")