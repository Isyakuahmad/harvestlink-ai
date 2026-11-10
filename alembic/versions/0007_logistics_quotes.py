"""Add logistics provider profiles, quotation requests and quotes.

Revision ID: 0007_logistics_quotes
Revises: 0006_procurement_transactions
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_logistics_quotes"
down_revision: str | None = "0006_procurement_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "logistics_provider_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("organization_name", sa.String(180), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("service_areas", sa.JSON(), nullable=False),
        sa.Column("transport_modes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_logistics_provider_profiles_user_id", "logistics_provider_profiles", ["user_id"])
    op.create_table(
        "logistics_quote_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("procurement_transactions.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("origin", sa.String(180), nullable=False),
        sa.Column("destination", sa.String(180), nullable=False),
        sa.Column("pickup_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cargo_description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_logistics_quote_requests_transaction_id", "logistics_quote_requests", ["transaction_id"])
    op.create_table(
        "logistics_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("logistics_quote_requests.id"), nullable=False),
        sa.Column("provider_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("estimated_days", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("buyer_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("farmer_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "provider_user_id", name="uq_logistics_quote_provider"),
    )
    op.create_index("ix_logistics_quotes_request_id", "logistics_quotes", ["request_id"])
    op.create_index("ix_logistics_quotes_provider_user_id", "logistics_quotes", ["provider_user_id"])


def downgrade() -> None:
    op.drop_index("ix_logistics_quotes_provider_user_id", table_name="logistics_quotes")
    op.drop_index("ix_logistics_quotes_request_id", table_name="logistics_quotes")
    op.drop_table("logistics_quotes")
    op.drop_index("ix_logistics_quote_requests_transaction_id", table_name="logistics_quote_requests")
    op.drop_table("logistics_quote_requests")
    op.drop_index("ix_logistics_provider_profiles_user_id", table_name="logistics_provider_profiles")
    op.drop_table("logistics_provider_profiles")
