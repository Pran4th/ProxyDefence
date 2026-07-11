"""add notification_preferences column to users

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notification_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                "'{\"critical_threat_alerts\": true, \"weekly_reports\": true, "
                "\"simulation_results\": false, \"system_updates\": true}'::jsonb"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_preferences")
