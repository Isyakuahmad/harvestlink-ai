"""Add reviewed market-price observations for market intelligence.

Revision ID: 0010_market_intelligence
Revises: 0009_aggregator_stock_deals
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_market_intelligence"
down_revision: str | None = "0009_aggregator_stock_deals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_price_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commodity", sa.String(100), nullable=False),
        sa.Column("market_name", sa.String(160), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("min_price", sa.Float(), nullable=False),
        sa.Column("max_price", sa.Float(), nullable=False),
        sa.Column("modal_price", sa.Float(), nullable=False),
        sa.Column("quality_grade", sa.String(100), nullable=False, server_default=""),
        sa.Column("source_name", sa.String(180), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="user_report"),
        sa.Column("verification_status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("commodity", "market_name", "state", "observed_on", "submitted_by_user_id"):
        op.create_index(f"ix_market_price_observations_{column}", "market_price_observations", [column])


def downgrade() -> None:
    for column in ("submitted_by_user_id", "observed_on", "state", "market_name", "commodity"):
        op.drop_index(f"ix_market_price_observations_{column}", table_name="market_price_observations")
    op.drop_table("market_price_observations")
