"""Create core GrowthOps tables.

Revision ID: 0001_create_core_tables
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(64), primary_key=True),
        sa.Column("signup_date", sa.Date(), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("preferred_device", sa.String(50), nullable=False),
        sa.Column("acquisition_channel", sa.String(100), nullable=False),
        sa.Column("customer_type", sa.String(50), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("product_id", sa.String(64), primary_key=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("device", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("campaign", sa.String(150), nullable=True),
        sa.Column("app_version", sa.String(50), nullable=False),
        sa.Column("landing_page", sa.String(255), nullable=False),
    )
    op.create_index("ix_sessions_customer_id", "sessions", ["customer_id"])
    op.create_index("ix_sessions_date", "sessions", ["date"])

    op.create_table(
        "events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
    )
    op.create_index("ix_events_session_id", "events", ["session_id"])
    op.create_index("ix_events_customer_id", "events", ["customer_id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])

    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("product_id", sa.String(64), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_margin", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("acquisition_channel", sa.String(100), nullable=False),
        sa.Column("campaign", sa.String(150), nullable=True),
        sa.Column("low_quality_acquisition", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_session_id", "orders", ["session_id"])
    op.create_index("ix_orders_product_id", "orders", ["product_id"])
    op.create_index("ix_orders_timestamp", "orders", ["timestamp"])
    op.create_index("ix_orders_date", "orders", ["date"])

    op.create_table(
        "payment_attempts",
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.session_id"), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("device", sa.String(50), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("app_version", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("payment_status", sa.String(50), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_payment_attempts_date", "payment_attempts", ["date"])

    op.create_table(
        "marketing_spend",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("channel", sa.String(100), primary_key=True),
        sa.Column("spend", sa.Numeric(14, 2), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("marketing_spend")
    op.drop_index("ix_payment_attempts_date", table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_index("ix_orders_date", table_name="orders")
    op.drop_index("ix_orders_timestamp", table_name="orders")
    op.drop_index("ix_orders_product_id", table_name="orders")
    op.drop_index("ix_orders_session_id", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_events_timestamp", table_name="events")
    op.drop_index("ix_events_customer_id", table_name="events")
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_sessions_date", table_name="sessions")
    op.drop_index("ix_sessions_customer_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("products")
    op.drop_table("customers")
