"""drop GFS retention columns (retention_days-only)

Revision ID: c3d6e9f4a2b7
Revises: b2c5d8e3f9a1
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d6e9f4a2b7"
down_revision: Union[str, None] = "b2c5d8e3f9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("backup_schedules", "retention_daily")
    op.drop_column("backup_schedules", "retention_weekly")
    op.drop_column("backup_schedules", "retention_monthly")


def downgrade() -> None:
    op.add_column("backup_schedules", sa.Column("retention_daily", sa.Integer(), nullable=False, server_default="7"))
    op.add_column("backup_schedules", sa.Column("retention_weekly", sa.Integer(), nullable=False, server_default="4"))
    op.add_column("backup_schedules", sa.Column("retention_monthly", sa.Integer(), nullable=False, server_default="3"))
