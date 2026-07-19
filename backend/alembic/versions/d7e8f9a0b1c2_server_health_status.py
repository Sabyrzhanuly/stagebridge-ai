"""server health status fields

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-06-25 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "servers",
        sa.Column("health_status", sa.String(length=20), nullable=False, server_default="unknown"),
    )
    op.add_column("servers", sa.Column("health_error", sa.Text(), nullable=True))
    op.add_column("servers", sa.Column("health_checked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "servers",
        sa.Column("health_fail_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("servers", "health_status", server_default=None)


def downgrade() -> None:
    op.drop_column("servers", "health_fail_count")
    op.drop_column("servers", "health_checked_at")
    op.drop_column("servers", "health_error")
    op.drop_column("servers", "health_status")
