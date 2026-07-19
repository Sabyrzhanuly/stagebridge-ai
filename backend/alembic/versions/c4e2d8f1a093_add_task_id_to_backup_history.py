"""add_task_id_to_backup_history

Revision ID: c4e2d8f1a093
Revises: b3f1a9e02c47
Create Date: 2026-04-25 20:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c4e2d8f1a093'
down_revision: Union[str, None] = 'b3f1a9e02c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('backup_history', sa.Column('task_id', sa.String(length=64), nullable=True, index=True))


def downgrade() -> None:
    op.drop_column('backup_history', 'task_id')
