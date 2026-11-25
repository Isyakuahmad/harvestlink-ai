"""Add aggregator offer, deal and reservation lifecycle.

Revision ID: 0009_aggregator_stock_deals
Revises: 0008_supply_chain_and_agent_traces
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_aggregator_stock_deals"
down_revision: str | None = "0008_supply_chain_and_agent_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite cannot ALTER an existing table to add/drop a constraint directly.
    # Alembic batch mode rebuilds the table safely for SQLite and remains valid
    # for other supported database dialects.
    with op.batch_alter_table("aggregator_stock_lots") as batch_op:
        batch_op.add_column(
            sa.Column("reserved_quantity", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint(
            "ck_aggregator_stock_reserved_range",
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
        )
    op.create_table(
        "aggregator_stock_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_lot_id", sa.Integer(), sa.ForeignKey("aggregator_stock_lots.id"), nullable=False),
        sa.Column("aggregator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("buyer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False), sa.Column("unit", sa.String(12), nullable=False),
        sa.Column("price_per_unit", sa.Float(), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""), sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("stock_lot_id", "aggregator_user_id", "buyer_user_id"):
        op.create_index(f"ix_aggregator_stock_offers_{column}", "aggregator_stock_offers", [column])
    op.create_table(
        "aggregator_stock_deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("aggregator_stock_offers.id"), nullable=False, unique=True),
        sa.Column("stock_lot_id", sa.Integer(), sa.ForeignKey("aggregator_stock_lots.id"), nullable=False),
        sa.Column("aggregator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("buyer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False), sa.Column("unit", sa.String(12), nullable=False),
        sa.Column("price_per_unit", sa.Float(), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("offer_id", "stock_lot_id", "aggregator_user_id", "buyer_user_id"):
        op.create_index(f"ix_aggregator_stock_deals_{column}", "aggregator_stock_deals", [column])
    op.create_table(
        "aggregator_stock_deal_events",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("deal_id", sa.Integer(), sa.ForeignKey("aggregator_stock_deals.id"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_aggregator_stock_deal_events_deal_id", "aggregator_stock_deal_events", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_aggregator_stock_deal_events_deal_id", table_name="aggregator_stock_deal_events")
    op.drop_table("aggregator_stock_deal_events")
    for column in ("buyer_user_id", "aggregator_user_id", "stock_lot_id", "offer_id"):
        op.drop_index(f"ix_aggregator_stock_deals_{column}", table_name="aggregator_stock_deals")
    op.drop_table("aggregator_stock_deals")
    for column in ("buyer_user_id", "aggregator_user_id", "stock_lot_id"):
        op.drop_index(f"ix_aggregator_stock_offers_{column}", table_name="aggregator_stock_offers")
    op.drop_table("aggregator_stock_offers")
    with op.batch_alter_table("aggregator_stock_lots") as batch_op:
        batch_op.drop_constraint("ck_aggregator_stock_reserved_range", type_="check")
        batch_op.drop_column("reserved_quantity")
