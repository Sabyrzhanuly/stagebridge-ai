"""add_minio_config

Revision ID: d5a7b2e3c841
Revises: c4e2d8f1a093
Create Date: 2026-04-25 20:55:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5a7b2e3c841'
down_revision: Union[str, None] = 'c4e2d8f1a093'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'minio_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=255), nullable=False),
        sa.Column('access_key', sa.String(length=255), nullable=False),
        sa.Column('secret_key', sa.String(length=255), nullable=False),
        sa.Column('bucket', sa.String(length=255), nullable=False),
        sa.Column('secure', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('minio_config')
