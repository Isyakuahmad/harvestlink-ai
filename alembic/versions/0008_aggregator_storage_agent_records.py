"""Add aggregator stock, independent storage and persisted agent traces.

Revision ID: 0008_supply_chain_and_agent_traces
Revises: 0007_logistics_quotes
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_supply_chain_and_agent_traces"
down_revision: str | None = "0007_logistics_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aggregator_stock_lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aggregator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("crop_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(12), nullable=False),
        sa.Column("quality_description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(180), nullable=False),
        sa.Column("source_listing_id", sa.Integer(), sa.ForeignKey("produce_listings.id")),
        sa.Column("ownership_reference", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_aggregator_stock_lots_aggregator_user_id", "aggregator_stock_lots", ["aggregator_user_id"])
    op.create_index("ix_aggregator_stock_lots_crop_name", "aggregator_stock_lots", ["crop_name"])
    op.create_table(
        "storage_operator_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("facility_name", sa.String(180), nullable=False),
        sa.Column("location", sa.String(180), nullable=False),
        sa.Column("capacity_kg", sa.Float(), nullable=False),
        sa.Column("accepted_commodities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_storage_operator_profiles_user_id", "storage_operator_profiles", ["user_id"])
    op.create_table(
        "storage_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_lot_id", sa.Integer(), sa.ForeignKey("aggregator_stock_lots.id"), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity_kg", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("fee_amount", sa.Float()),
        sa.Column("fee_currency", sa.String(3)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_storage_bookings_stock_lot_id", "storage_bookings", ["stock_lot_id"])
    op.create_index("ix_storage_bookings_operator_user_id", "storage_bookings", ["operator_user_id"])
    op.create_index("ix_storage_bookings_requested_by_user_id", "storage_bookings", ["requested_by_user_id"])
    op.create_table(
        "agent_execution_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_name", sa.String(60), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("events_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_execution_records_workflow_run_id", "agent_execution_records", ["workflow_run_id"])
    op.create_index("ix_agent_execution_records_requested_by_user_id", "agent_execution_records", ["requested_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_execution_records_requested_by_user_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_workflow_run_id", table_name="agent_execution_records")
    op.drop_table("agent_execution_records")
    op.drop_index("ix_storage_bookings_requested_by_user_id", table_name="storage_bookings")
    op.drop_index("ix_storage_bookings_operator_user_id", table_name="storage_bookings")
    op.drop_index("ix_storage_bookings_stock_lot_id", table_name="storage_bookings")
    op.drop_table("storage_bookings")
    op.drop_index("ix_storage_operator_profiles_user_id", table_name="storage_operator_profiles")
    op.drop_table("storage_operator_profiles")
    op.drop_index("ix_aggregator_stock_lots_crop_name", table_name="aggregator_stock_lots")
    op.drop_index("ix_aggregator_stock_lots_aggregator_user_id", table_name="aggregator_stock_lots")
    op.drop_table("aggregator_stock_lots")
