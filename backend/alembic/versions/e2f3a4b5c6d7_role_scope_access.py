"""role scope access per org

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-16 14:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "role_server_access" not in tables:
        op.create_table(
            "role_server_access",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("org_role", sa.String(length=50), nullable=False),
            sa.Column("server_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id", "org_role", "server_id",
                name="uq_role_server_access",
            ),
        )
        op.create_index("ix_role_server_access_organization_id", "role_server_access", ["organization_id"])
        op.create_index("ix_role_server_access_org_role", "role_server_access", ["org_role"])
        op.create_index("ix_role_server_access_server_id", "role_server_access", ["server_id"])

    if "role_database_access" not in tables:
        op.create_table(
            "role_database_access",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("org_role", sa.String(length=50), nullable=False),
            sa.Column("server_id", sa.Integer(), nullable=False),
            sa.Column("database_name", sa.String(length=255), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id", "org_role", "server_id", "database_name",
                name="uq_role_database_access",
            ),
        )
        op.create_index("ix_role_database_access_organization_id", "role_database_access", ["organization_id"])
        op.create_index("ix_role_database_access_org_role", "role_database_access", ["org_role"])
        op.create_index("ix_role_database_access_server_id", "role_database_access", ["server_id"])

    if "member_server_access" in tables:
        op.execute(
            """
            insert into role_server_access (organization_id, org_role, server_id)
            select distinct m.organization_id, m.org_role, msa.server_id
            from member_server_access msa
            join organization_members m on m.id = msa.member_id
            on conflict on constraint uq_role_server_access do nothing
            """
        )

    if "member_database_access" in tables:
        op.execute(
            """
            insert into role_database_access (organization_id, org_role, server_id, database_name)
            select distinct m.organization_id, m.org_role, mda.server_id, mda.database_name
            from member_database_access mda
            join organization_members m on m.id = mda.member_id
            on conflict on constraint uq_role_database_access do nothing
            """
        )
        op.drop_index("ix_member_database_access_member_id", table_name="member_database_access")
        op.drop_table("member_database_access")

    if "member_server_access" in tables:
        op.drop_index("ix_member_server_access_member_id", table_name="member_server_access")
        op.drop_table("member_server_access")


def downgrade() -> None:
    op.create_table(
        "member_server_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["organization_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "server_id", name="uq_member_server_access"),
    )
    op.create_index("ix_member_server_access_member_id", "member_server_access", ["member_id"])

    op.create_table(
        "member_database_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["organization_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "server_id", "database_name",
            name="uq_member_database_access",
        ),
    )
    op.create_index("ix_member_database_access_member_id", "member_database_access", ["member_id"])

    op.drop_index("ix_role_database_access_server_id", table_name="role_database_access")
    op.drop_index("ix_role_database_access_org_role", table_name="role_database_access")
    op.drop_index("ix_role_database_access_organization_id", table_name="role_database_access")
    op.drop_table("role_database_access")

    op.drop_index("ix_role_server_access_server_id", table_name="role_server_access")
    op.drop_index("ix_role_server_access_org_role", table_name="role_server_access")
    op.drop_index("ix_role_server_access_organization_id", table_name="role_server_access")
    op.drop_table("role_server_access")
