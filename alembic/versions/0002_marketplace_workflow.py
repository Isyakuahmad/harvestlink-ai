"""Add marketplace listings, buyer requirements and agent workflow traces.

Revision ID: 0002_marketplace_workflow
Revises: 0001_initial_users
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_marketplace_workflow"
down_revision: str | None = "0001_initial_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "buyer_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("buyer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("crop_name", sa.String(100), nullable=False),
        sa.Column("min_quantity", sa.Float(), nullable=False),
        sa.Column("max_quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("quality_requirements", sa.Text(), nullable=False),
        sa.Column("location", sa.String(180), nullable=False),
        sa.Column("max_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_buyer_requirements_buyer_user_id", "buyer_requirements", ["buyer_user_id"])
    op.create_index("ix_buyer_requirements_crop_name", "buyer_requirements", ["crop_name"])

    op.create_table(
        "produce_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("crop_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("quality_description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(180), nullable=False),
        sa.Column("available_on", sa.Date(), nullable=False),
        sa.Column("asking_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_produce_listings_farmer_user_id", "produce_listings", ["farmer_user_id"])
    op.create_index("ix_produce_listings_crop_name", "produce_listings", ["crop_name"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("produce_listings.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_runs_listing_id", "workflow_runs", ["listing_id"])

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("agent_name", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_tasks_workflow_run_id", "agent_tasks", ["workflow_run_id"])

    op.create_table(
        "match_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("buyer_requirement_id", sa.Integer(), sa.ForeignKey("buyer_requirements.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_match_candidates_workflow_run_id", "match_candidates", ["workflow_run_id"])
    op.create_index("ix_match_candidates_buyer_requirement_id", "match_candidates", ["buyer_requirement_id"])


def downgrade() -> None:
    op.drop_table("match_candidates")
    op.drop_table("agent_tasks")
    op.drop_index("ix_workflow_runs_listing_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_produce_listings_crop_name", table_name="produce_listings")
    op.drop_index("ix_produce_listings_farmer_user_id", table_name="produce_listings")
    op.drop_table("produce_listings")
    op.drop_index("ix_buyer_requirements_crop_name", table_name="buyer_requirements")
    op.drop_index("ix_buyer_requirements_buyer_user_id", table_name="buyer_requirements")
    op.drop_table("buyer_requirements")
