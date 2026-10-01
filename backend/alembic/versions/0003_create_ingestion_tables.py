"""Create ingestion tracking tables.

Revision ID: 0003_create_ingestion_tables
Revises: 0002_create_uploads
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_create_ingestion_tables"
down_revision: Union[str, None] = "0002_create_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.upload_id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_ingestion_runs_upload_id", "ingestion_runs", ["upload_id"])

    op.create_table(
        "ingestion_errors",
        sa.Column("error_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("error_id"),
    )
    op.create_index("ix_ingestion_errors_run_id", "ingestion_errors", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_errors_run_id", table_name="ingestion_errors")
    op.drop_table("ingestion_errors")
    op.drop_index("ix_ingestion_runs_upload_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
