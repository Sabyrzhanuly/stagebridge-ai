"""minio_config_per_server

Revision ID: e6c3f8a2b104
Revises: d5a7b2e3c841
Create Date: 2026-04-25 22:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e6c3f8a2b104'
down_revision: Union[str, None] = 'd5a7b2e3c841'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM minio_config")
    op.add_column('minio_config', sa.Column('server_id', sa.Integer(), nullable=False))
    op.create_unique_constraint('uq_minio_config_server_id', 'minio_config', ['server_id'])
    op.create_foreign_key(
        'fk_minio_config_server_id',
        'minio_config', 'servers',
        ['server_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_minio_config_server_id', 'minio_config', type_='foreignkey')
    op.drop_constraint('uq_minio_config_server_id', 'minio_config', type_='unique')
    op.drop_column('minio_config', 'server_id')
