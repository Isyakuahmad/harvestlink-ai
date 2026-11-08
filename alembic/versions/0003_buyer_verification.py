"""Add buyer profiles and human verification workflow.

Revision ID: 0003_buyer_verification
Revises: 0002_marketplace_workflow
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_buyer_verification"
down_revision: str | None = "0002_marketplace_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="unverified"),
    )
    op.create_table(
        "buyer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("organization_name", sa.String(180), nullable=False),
        sa.Column("buyer_type", sa.String(40), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("location", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_buyer_profiles_user_id", "buyer_profiles", ["user_id"])
    op.execute(
        "INSERT INTO verification_cases (subject_type, subject_id, submitted_by_user_id, status, created_at) "
        "SELECT 'user', id, id, 'pending', CURRENT_TIMESTAMP FROM users WHERE role IN ('farmer', 'buyer')"
    )
    op.create_table(
        "verification_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_cases_subject_id", "verification_cases", ["subject_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("subject_type", sa.String(30), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_index("ix_verification_cases_subject_id", table_name="verification_cases")
    op.drop_table("verification_cases")
    op.drop_index("ix_buyer_profiles_user_id", table_name="buyer_profiles")
    op.drop_table("buyer_profiles")
    op.drop_column("users", "verification_status")
