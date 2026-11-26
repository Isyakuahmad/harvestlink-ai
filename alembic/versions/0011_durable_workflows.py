"""Add durable workflow scheduling, retries and idempotency.

Revision ID: 0011_durable_workflows
Revises: 0010_market_intelligence
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_durable_workflows"
down_revision: str | None = "0010_market_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_runs", sa.Column("farmer_user_id", sa.Integer(), nullable=True))
    op.add_column("workflow_runs", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column("workflow_runs", sa.Column("request_hash", sa.String(64), nullable=True))
    op.add_column("workflow_runs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("workflow_runs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("workflow_runs", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_runs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_runs", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_runs_farmer_user_id", "workflow_runs", "users",
        ["farmer_user_id"], ["id"],
    )
    op.create_index("ix_workflow_runs_farmer_user_id", "workflow_runs", ["farmer_user_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_unique_constraint(
        "uq_workflow_farmer_idempotency", "workflow_runs",
        ["farmer_user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_workflow_farmer_idempotency", "workflow_runs", type_="unique")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_farmer_user_id", table_name="workflow_runs")
    op.drop_constraint("fk_workflow_runs_farmer_user_id", "workflow_runs", type_="foreignkey")
    for column in (
        "last_error", "locked_at", "next_retry_at", "max_attempts",
        "attempt_count", "request_hash", "idempotency_key", "farmer_user_id",
    ):
        op.drop_column("workflow_runs", column)
