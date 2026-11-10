"""Add import sessions and dataset type metadata to uploads.

Revision ID: 0005_import_sessions
Revises: 0004_generic_dataset_records
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_import_sessions"
down_revision: Union[str, None] = "0004_generic_dataset_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_sessions",
        sa.Column("import_session_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("import_session_id"),
    )
    op.add_column("uploads", sa.Column("import_session_id", sa.UUID(), nullable=True))
    op.add_column("uploads", sa.Column("dataset_type", sa.String(length=50), nullable=True))
    op.create_foreign_key(
        "fk_uploads_import_session_id",
        "uploads",
        "import_sessions",
        ["import_session_id"],
        ["import_session_id"],
    )
    op.create_index("ix_uploads_import_session_id", "uploads", ["import_session_id"])


def downgrade() -> None:
    op.drop_index("ix_uploads_import_session_id", table_name="uploads")
    op.drop_constraint("fk_uploads_import_session_id", "uploads", type_="foreignkey")
    op.drop_column("uploads", "dataset_type")
    op.drop_column("uploads", "import_session_id")
    op.drop_table("import_sessions")
