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
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.add_column(sa.Column("farmer_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("request_hash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"))
        batch_op.add_column(sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
    op.execute(
        "UPDATE workflow_runs SET farmer_user_id = "
        "(SELECT farmer_user_id FROM produce_listings "
        "WHERE produce_listings.id = workflow_runs.listing_id) "
        "WHERE farmer_user_id IS NULL"
    )
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.create_foreign_key(
            "fk_workflow_runs_farmer_user_id", "users", ["farmer_user_id"], ["id"]
        )
        batch_op.create_index("ix_workflow_runs_farmer_user_id", ["farmer_user_id"])
        batch_op.create_index("ix_workflow_runs_status", ["status"])
        batch_op.create_unique_constraint(
            "uq_workflow_farmer_idempotency", ["farmer_user_id", "idempotency_key"]
        )

def downgrade() -> None:
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint("uq_workflow_farmer_idempotency", type_="unique")
        batch_op.drop_index("ix_workflow_runs_status")
        batch_op.drop_index("ix_workflow_runs_farmer_user_id")
        batch_op.drop_constraint("fk_workflow_runs_farmer_user_id", type_="foreignkey")
        for column in (
            "last_error", "locked_at", "next_retry_at", "max_attempts",
            "attempt_count", "request_hash", "idempotency_key", "farmer_user_id",
        ):
            batch_op.drop_column(column)
