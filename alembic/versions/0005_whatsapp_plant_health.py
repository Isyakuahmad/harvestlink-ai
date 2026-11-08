"""Add WhatsApp channel, pending farm entries and plant health cases.

Revision ID: 0005_whatsapp_plant_health
Revises: 0004_farmer_evidence_ledger
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_whatsapp_plant_health"
down_revision: str | None = "0004_farmer_evidence_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_channel_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("phone_e164", sa.String(20), nullable=False, unique=True),
        sa.Column("link_code_hash", sa.String(64), nullable=True),
        sa.Column("link_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_whatsapp_channel_links_user_id", "whatsapp_channel_links", ["user_id"])
    op.create_index("ix_whatsapp_channel_links_phone_e164", "whatsapp_channel_links", ["phone_e164"])
    op.create_table(
        "whatsapp_inbound_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_message_id", sa.String(160), nullable=False, unique=True),
        sa.Column("from_phone", sa.String(20), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("media_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_whatsapp_inbound_messages_provider_message_id", "whatsapp_inbound_messages", ["provider_message_id"])
    op.create_index("ix_whatsapp_inbound_messages_from_phone", "whatsapp_inbound_messages", ["from_phone"])
    op.create_table(
        "farmer_pending_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("farm_seasons.id"), nullable=False),
        sa.Column("entry_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farmer_pending_entries_farmer_user_id", "farmer_pending_entries", ["farmer_user_id"])
    op.create_index("ix_farmer_pending_entries_season_id", "farmer_pending_entries", ["season_id"])
    op.create_table(
        "plant_health_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("crop_name", sa.String(100), nullable=False),
        sa.Column("farm_location", sa.String(180), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=False),
        sa.Column("affected_area_percent", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("image_media_id", sa.String(200), nullable=True),
        sa.Column("image_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("guidance_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_plant_health_cases_farmer_user_id", "plant_health_cases", ["farmer_user_id"])


def downgrade() -> None:
    op.drop_index("ix_plant_health_cases_farmer_user_id", table_name="plant_health_cases")
    op.drop_table("plant_health_cases")
    op.drop_index("ix_farmer_pending_entries_season_id", table_name="farmer_pending_entries")
    op.drop_index("ix_farmer_pending_entries_farmer_user_id", table_name="farmer_pending_entries")
    op.drop_table("farmer_pending_entries")
    op.drop_index("ix_whatsapp_inbound_messages_from_phone", table_name="whatsapp_inbound_messages")
    op.drop_index("ix_whatsapp_inbound_messages_provider_message_id", table_name="whatsapp_inbound_messages")
    op.drop_table("whatsapp_inbound_messages")
    op.drop_index("ix_whatsapp_channel_links_phone_e164", table_name="whatsapp_channel_links")
    op.drop_index("ix_whatsapp_channel_links_user_id", table_name="whatsapp_channel_links")
    op.drop_table("whatsapp_channel_links")
