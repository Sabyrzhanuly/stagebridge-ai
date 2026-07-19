"""per-member scope access + 3 flat org roles

Возврат к доступу, привязанному к участнику (а не к роли):
- новые таблицы member_server_access / member_database_access;
- доступ роли раскрывается на всех участников этой роли;
- бывшие dba (implicit «все серверы») получают явный доступ ко всем серверам,
  т.к. новый Оператор — scoped;
- роли dba/devops -> operator (модель из 3 ролей: org_admin/operator/viewer);
- старые role_server_access / role_database_access удаляются.

Revision ID: e7f0a1b2c3d4
Revises: c3d6e9f4a2b7
Create Date: 2026-07-12 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7f0a1b2c3d4"
down_revision: Union[str, None] = "c3d6e9f4a2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "member_server_access" not in tables:
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
        op.create_index("ix_member_server_access_server_id", "member_server_access", ["server_id"])

    if "member_database_access" not in tables:
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
        op.create_index("ix_member_database_access_server_id", "member_database_access", ["server_id"])

    # 1) Раскрываем доступ роли -> на каждого участника этой роли.
    if "role_server_access" in tables:
        op.execute(
            """
            insert into member_server_access (member_id, server_id)
            select distinct m.id, rsa.server_id
            from role_server_access rsa
            join organization_members m
              on m.organization_id = rsa.organization_id
             and m.org_role = rsa.org_role
            on conflict on constraint uq_member_server_access do nothing
            """
        )

    if "role_database_access" in tables:
        op.execute(
            """
            insert into member_database_access (member_id, server_id, database_name)
            select distinct m.id, rda.server_id, rda.database_name
            from role_database_access rda
            join organization_members m
              on m.organization_id = rda.organization_id
             and m.org_role = rda.org_role
            on conflict on constraint uq_member_database_access do nothing
            """
        )

    # 2) Бывшие dba видели все серверы неявно; новый Оператор — scoped,
    #    поэтому выдаём им явный доступ ко всем текущим серверам организации.
    #    (org_admin остаётся implicit-all — ему backfill не нужен.)
    op.execute(
        """
        insert into member_server_access (member_id, server_id)
        select m.id, s.id
        from organization_members m
        join servers s on s.organization_id = m.organization_id
        where m.org_role = 'dba'
        on conflict on constraint uq_member_server_access do nothing
        """
    )

    # 3) Ремап 5 ролей -> 3 (org_admin/operator/viewer).
    op.execute("update organization_members set org_role = 'operator' where org_role in ('dba', 'devops')")

    # 4) Старые role-таблицы больше не нужны.
    if "role_database_access" in tables:
        for idx in ("ix_role_database_access_server_id", "ix_role_database_access_org_role", "ix_role_database_access_organization_id"):
            try:
                op.drop_index(idx, table_name="role_database_access")
            except Exception:
                pass
        op.drop_table("role_database_access")

    if "role_server_access" in tables:
        for idx in ("ix_role_server_access_server_id", "ix_role_server_access_org_role", "ix_role_server_access_organization_id"):
            try:
                op.drop_index(idx, table_name="role_server_access")
            except Exception:
                pass
        op.drop_table("role_server_access")


def downgrade() -> None:
    # Best-effort: восстанавливаем role-таблицы и наполняем их из member-доступа
    # по текущей роли участника. Разбивку dba/devops восстановить нельзя.
    op.create_table(
        "role_server_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("org_role", sa.String(length=50), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "org_role", "server_id", name="uq_role_server_access"),
    )
    op.create_index("ix_role_server_access_organization_id", "role_server_access", ["organization_id"])
    op.create_index("ix_role_server_access_org_role", "role_server_access", ["org_role"])
    op.create_index("ix_role_server_access_server_id", "role_server_access", ["server_id"])

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

    op.execute(
        """
        insert into role_server_access (organization_id, org_role, server_id)
        select distinct m.organization_id, m.org_role, msa.server_id
        from member_server_access msa
        join organization_members m on m.id = msa.member_id
        on conflict on constraint uq_role_server_access do nothing
        """
    )
    op.execute(
        """
        insert into role_database_access (organization_id, org_role, server_id, database_name)
        select distinct m.organization_id, m.org_role, mda.server_id, mda.database_name
        from member_database_access mda
        join organization_members m on m.id = mda.member_id
        on conflict on constraint uq_role_database_access do nothing
        """
    )

    op.drop_index("ix_member_database_access_server_id", table_name="member_database_access")
    op.drop_index("ix_member_database_access_member_id", table_name="member_database_access")
    op.drop_table("member_database_access")
    op.drop_index("ix_member_server_access_server_id", table_name="member_server_access")
    op.drop_index("ix_member_server_access_member_id", table_name="member_server_access")
    op.drop_table("member_server_access")
