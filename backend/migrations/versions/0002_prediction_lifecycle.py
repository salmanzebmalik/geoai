"""Add durable prediction lifecycle metadata.

Revision ID: 0002_prediction_lifecycle
Revises: 0001_existing_schema
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_prediction_lifecycle"
down_revision: str | None = "0001_existing_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "segmentation_queries",
        sa.Column(
            "request_payload",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "status_message",
            sa.String(),
            nullable=True,
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "error_code",
            sa.String(),
            nullable=True,
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "error_message",
            sa.String(),
            nullable=True,
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "segmentation_queries",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Mark existing completed predictions correctly.
    op.execute(
        """
        UPDATE segmentation_queries
        SET
            progress_percent = 100,
            status_message = 'Historical completed prediction'
        WHERE status = 'completed'
        """
    )

    op.create_index(
        "idx_segmentation_queries_status_created_at",
        "segmentation_queries",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_segmentation_queries_status_created_at",
        table_name="segmentation_queries",
    )

    op.drop_column(
        "segmentation_queries",
        "updated_at",
    )
    op.drop_column(
        "segmentation_queries",
        "completed_at",
    )
    op.drop_column(
        "segmentation_queries",
        "started_at",
    )
    op.drop_column(
        "segmentation_queries",
        "error_message",
    )
    op.drop_column(
        "segmentation_queries",
        "error_code",
    )
    op.drop_column(
        "segmentation_queries",
        "status_message",
    )
    op.drop_column(
        "segmentation_queries",
        "progress_percent",
    )
    op.drop_column(
        "segmentation_queries",
        "request_payload",
    )