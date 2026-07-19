"""s3 storage org catalog

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-16 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("minio_config", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.add_column("minio_config", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column(
        "minio_config",
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.execute(
        """
        UPDATE minio_config mc
        SET organization_id = s.organization_id,
            name = 'S3 ' || s.name
        FROM servers s
        WHERE mc.server_id = s.id
        """
    )

    op.add_column("servers", sa.Column("storage_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE servers s
        SET storage_id = mc.id
        FROM minio_config mc
        WHERE mc.server_id = s.id
        """
    )

    op.drop_constraint("fk_minio_config_server_id", "minio_config", type_="foreignkey")
    op.drop_constraint("uq_minio_config_server_id", "minio_config", type_="unique")
    op.drop_column("minio_config", "server_id")

    op.alter_column("minio_config", "organization_id", nullable=False)
    op.alter_column("minio_config", "name", nullable=False)

    op.create_foreign_key(
        "fk_minio_config_organization_id",
        "minio_config",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_minio_config_organization_id", "minio_config", ["organization_id"])
    op.create_unique_constraint("uq_minio_config_org_name", "minio_config", ["organization_id", "name"])

    op.create_foreign_key(
        "fk_servers_storage_id",
        "servers",
        "minio_config",
        ["storage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_servers_storage_id", "servers", ["storage_id"])

    op.add_column("backup_history", sa.Column("storage_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE backup_history bh
        SET storage_id = s.storage_id
        FROM servers s
        WHERE bh.server_id = s.id
          AND s.storage_id IS NOT NULL
        """
    )
    op.create_foreign_key(
        "fk_backup_history_storage_id",
        "backup_history",
        "minio_config",
        ["storage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_backup_history_storage_id", "backup_history", ["storage_id"])


def downgrade() -> None:
    op.drop_index("ix_backup_history_storage_id", table_name="backup_history")
    op.drop_constraint("fk_backup_history_storage_id", "backup_history", type_="foreignkey")
    op.drop_column("backup_history", "storage_id")

    op.drop_index("ix_servers_storage_id", table_name="servers")
    op.drop_constraint("fk_servers_storage_id", "servers", type_="foreignkey")
    op.drop_column("servers", "storage_id")

    op.drop_constraint("uq_minio_config_org_name", "minio_config", type_="unique")
    op.drop_index("ix_minio_config_organization_id", table_name="minio_config")
    op.drop_constraint("fk_minio_config_organization_id", "minio_config", type_="foreignkey")

    op.add_column("minio_config", sa.Column("server_id", sa.Integer(), nullable=True))
    op.drop_column("minio_config", "created_at")
    op.drop_column("minio_config", "name")
    op.drop_column("minio_config", "organization_id")
