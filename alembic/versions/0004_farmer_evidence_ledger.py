"""Add farmer farm records, evidence and consented report sharing.

Revision ID: 0004_farmer_evidence_ledger
Revises: 0003_buyer_verification
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_farmer_evidence_ledger"
down_revision: str | None = "0003_buyer_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "farm_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("farm_name", sa.String(160), nullable=False),
        sa.Column("location", sa.String(180), nullable=False),
        sa.Column("acreage", sa.Float(), nullable=False),
        sa.Column("acreage_unit", sa.String(20), nullable=False),
        sa.Column("land_access", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farm_profiles_farmer_user_id", "farm_profiles", ["farmer_user_id"])
    op.create_table(
        "farm_seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("farm_profile_id", sa.Integer(), sa.ForeignKey("farm_profiles.id"), nullable=False),
        sa.Column("crop_name", sa.String(100), nullable=False),
        sa.Column("season_name", sa.String(100), nullable=False),
        sa.Column("planted_area", sa.Float(), nullable=False),
        sa.Column("area_unit", sa.String(20), nullable=False),
        sa.Column("planting_date", sa.Date(), nullable=True),
        sa.Column("expected_harvest_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farm_seasons_farmer_user_id", "farm_seasons", ["farmer_user_id"])
    op.create_index("ix_farm_seasons_farm_profile_id", "farm_seasons", ["farm_profile_id"])
    op.create_table(
        "farm_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("farm_seasons.id"), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("quantity_unit", sa.String(30), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("source_channel", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farm_activities_farmer_user_id", "farm_activities", ["farmer_user_id"])
    op.create_index("ix_farm_activities_season_id", "farm_activities", ["season_id"])
    op.create_table(
        "farm_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("farm_activities.id"), nullable=False),
        sa.Column("evidence_type", sa.String(30), nullable=False),
        sa.Column("evidence_uri", sa.Text(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("verification_level", sa.String(30), nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farm_evidence_farmer_user_id", "farm_evidence", ["farmer_user_id"])
    op.create_index("ix_farm_evidence_activity_id", "farm_evidence", ["activity_id"])
    op.create_table(
        "farm_share_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("farm_seasons.id"), nullable=True),
        sa.Column("recipient_name", sa.String(160), nullable=False),
        sa.Column("recipient_type", sa.String(40), nullable=False),
        sa.Column("purpose", sa.String(300), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farm_share_grants_farmer_user_id", "farm_share_grants", ["farmer_user_id"])
    op.create_index("ix_farm_share_grants_token_hash", "farm_share_grants", ["token_hash"])
    op.create_table(
        "farm_share_accesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grant_id", sa.Integer(), sa.ForeignKey("farm_share_grants.id"), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_type", sa.String(30), nullable=False),
    )
    op.create_index("ix_farm_share_accesses_grant_id", "farm_share_accesses", ["grant_id"])


def downgrade() -> None:
    op.drop_table("farm_share_accesses")
    op.drop_index("ix_farm_share_grants_token_hash", table_name="farm_share_grants")
    op.drop_index("ix_farm_share_grants_farmer_user_id", table_name="farm_share_grants")
    op.drop_table("farm_share_grants")
    op.drop_index("ix_farm_evidence_activity_id", table_name="farm_evidence")
    op.drop_index("ix_farm_evidence_farmer_user_id", table_name="farm_evidence")
    op.drop_table("farm_evidence")
    op.drop_index("ix_farm_activities_season_id", table_name="farm_activities")
    op.drop_index("ix_farm_activities_farmer_user_id", table_name="farm_activities")
    op.drop_table("farm_activities")
    op.drop_index("ix_farm_seasons_farm_profile_id", table_name="farm_seasons")
    op.drop_index("ix_farm_seasons_farmer_user_id", table_name="farm_seasons")
    op.drop_table("farm_seasons")
    op.drop_index("ix_farm_profiles_farmer_user_id", table_name="farm_profiles")
    op.drop_table("farm_profiles")
