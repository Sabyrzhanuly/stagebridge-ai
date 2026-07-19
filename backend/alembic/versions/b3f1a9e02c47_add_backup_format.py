"""add_backup_format

Revision ID: b3f1a9e02c47
Revises: 292ec41c805c
Create Date: 2026-04-25 20:35:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3f1a9e02c47'
down_revision: Union[str, None] = '292ec41c805c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('backup_history', sa.Column('backup_format', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('backup_history', 'backup_format')
