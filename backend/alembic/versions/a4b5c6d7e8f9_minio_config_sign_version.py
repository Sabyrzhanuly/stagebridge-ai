"""minio_config sign_version for ServerSpace S3 V2

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-06-25 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "minio_config",
        sa.Column("sign_version", sa.String(length=8), nullable=False, server_default="v4"),
    )
    op.alter_column("minio_config", "sign_version", server_default=None)


def downgrade() -> None:
    op.drop_column("minio_config", "sign_version")
