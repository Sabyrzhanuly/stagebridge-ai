"""minio_config api_type swift

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-06-25 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "minio_config",
        sa.Column("api_type", sa.String(length=8), nullable=False, server_default="s3"),
    )
    op.add_column(
        "minio_config",
        sa.Column("swift_project", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "minio_config",
        sa.Column("swift_domain", sa.String(length=64), nullable=True),
    )
    op.alter_column("minio_config", "api_type", server_default=None)


def downgrade() -> None:
    op.drop_column("minio_config", "swift_domain")
    op.drop_column("minio_config", "swift_project")
    op.drop_column("minio_config", "api_type")
