"""Store arbitrary uploaded dataset rows as JSON records.

Revision ID: 0004_generic_dataset_records
Revises: 0003_create_ingestion_tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_generic_dataset_records"
down_revision: Union[str, None] = "0003_create_ingestion_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generic_dataset_records",
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.upload_id"]),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index("ix_generic_dataset_records_upload_id", "generic_dataset_records", ["upload_id"])


def downgrade() -> None:
    op.drop_index("ix_generic_dataset_records_upload_id", table_name="generic_dataset_records")
    op.drop_table("generic_dataset_records")
