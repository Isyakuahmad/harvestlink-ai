"""Add buyer interest and mutually confirmed procurement transactions.

Revision ID: 0006_procurement_transactions
Revises: 0005_whatsapp_plant_health
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_procurement_transactions"
down_revision: str | None = "0005_whatsapp_plant_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "buyer_interests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("match_candidate_id", sa.Integer(), sa.ForeignKey("match_candidates.id"), nullable=False),
        sa.Column("buyer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("buyer_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("farmer_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("match_candidate_id", name="uq_buyer_interest_match"),
    )
    op.create_index("ix_buyer_interests_match_candidate_id", "buyer_interests", ["match_candidate_id"])
    op.create_index("ix_buyer_interests_buyer_user_id", "buyer_interests", ["buyer_user_id"])
    op.create_index("ix_buyer_interests_farmer_user_id", "buyer_interests", ["farmer_user_id"])

    op.create_table(
        "procurement_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interest_id", sa.Integer(), sa.ForeignKey("buyer_interests.id"), nullable=False, unique=True),
        sa.Column("buyer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("produce_listings.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="terms_proposed"),
        sa.Column("proposed_terms_json", sa.JSON(), nullable=False),
        sa.Column("agreed_terms_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_procurement_transactions_interest_id", "procurement_transactions", ["interest_id"])
    op.create_index("ix_procurement_transactions_buyer_user_id", "procurement_transactions", ["buyer_user_id"])
    op.create_index("ix_procurement_transactions_farmer_user_id", "procurement_transactions", ["farmer_user_id"])
    op.create_index("ix_procurement_transactions_listing_id", "procurement_transactions", ["listing_id"])

    op.create_table(
        "transaction_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("procurement_transactions.id"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transaction_events_transaction_id", "transaction_events", ["transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_transaction_events_transaction_id", table_name="transaction_events")
    op.drop_table("transaction_events")
    op.drop_index("ix_procurement_transactions_listing_id", table_name="procurement_transactions")
    op.drop_index("ix_procurement_transactions_farmer_user_id", table_name="procurement_transactions")
    op.drop_index("ix_procurement_transactions_buyer_user_id", table_name="procurement_transactions")
    op.drop_index("ix_procurement_transactions_interest_id", table_name="procurement_transactions")
    op.drop_table("procurement_transactions")
    op.drop_index("ix_buyer_interests_farmer_user_id", table_name="buyer_interests")
    op.drop_index("ix_buyer_interests_buyer_user_id", table_name="buyer_interests")
    op.drop_index("ix_buyer_interests_match_candidate_id", table_name="buyer_interests")
    op.drop_table("buyer_interests")
