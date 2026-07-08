"""add copilot conversation tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "copilot_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET_NULL")),
        sa.Column("title", sa.Text(), nullable=False, server_default="New Chat"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_copilot_messages_conversation_id", "copilot_messages", ["conversation_id"])
    op.create_index("idx_copilot_conversations_user_id", "copilot_conversations", ["user_id"])
    op.create_index("idx_copilot_conversations_updated_at", "copilot_conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_table("copilot_messages")
    op.drop_table("copilot_conversations")
