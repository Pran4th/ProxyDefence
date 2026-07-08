"""add energy intelligence bridge tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "energy_entity_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_text", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("energy_asset_type", sa.String(50), nullable=False),
        sa.Column("energy_asset_uuid", sa.Uuid(), nullable=False),
        sa.Column("energy_asset_name", sa.Text(), nullable=False),
        sa.Column("energy_asset_slug", sa.Text(), nullable=False),
        sa.Column("match_method", sa.String(20), server_default="exact"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "article_energy_enrichments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("locations", sa.JSON(), server_default="[]"),
        sa.Column("infrastructure", sa.JSON(), server_default="[]"),
        sa.Column("organizations", sa.JSON(), server_default="[]"),
        sa.Column("commodities", sa.JSON(), server_default="[]"),
        sa.Column("infrastructure_events", sa.JSON(), server_default="[]"),
        sa.Column("context", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_energy_entity_mappings_article_id", "energy_entity_mappings", ["article_id"])
    op.create_index("idx_energy_entity_mappings_entity_text", "energy_entity_mappings", ["entity_text"])
    op.create_index("idx_energy_entity_mappings_asset_type", "energy_entity_mappings", ["energy_asset_type"])
    op.create_index("idx_energy_entity_mappings_asset_uuid", "energy_entity_mappings", ["energy_asset_uuid"])
    op.create_index("idx_article_energy_enrichments_article_id", "article_energy_enrichments", ["article_id"])


def downgrade() -> None:
    op.drop_table("article_energy_enrichments")
    op.drop_table("energy_entity_mappings")
