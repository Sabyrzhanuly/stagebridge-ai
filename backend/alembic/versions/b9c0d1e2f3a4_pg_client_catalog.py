"""pg_client_catalog

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "pg_client_catalog" not in insp.get_table_names():
        op.create_table(
            "pg_client_catalog",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("major_version", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("major_version", name="uq_pg_client_catalog_major"),
        )

    indexes = {idx["name"] for idx in insp.get_indexes("pg_client_catalog")}
    if "ix_pg_client_catalog_major_version" not in indexes:
        op.create_index("ix_pg_client_catalog_major_version", "pg_client_catalog", ["major_version"])

    op.execute(
        """
        insert into pg_client_catalog (major_version, source, created_at)
        select distinct pg_major_version, 'requested', now()
        from servers
        where pg_major_version is not null
        on conflict (major_version) do nothing
        """
    )


def downgrade() -> None:
    op.drop_index("ix_pg_client_catalog_major_version", table_name="pg_client_catalog")
    op.drop_table("pg_client_catalog")
