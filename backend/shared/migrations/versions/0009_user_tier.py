"""add tier column to users (free/premium gating)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
    )


def downgrade() -> None:
    op.drop_column("users", "tier")
