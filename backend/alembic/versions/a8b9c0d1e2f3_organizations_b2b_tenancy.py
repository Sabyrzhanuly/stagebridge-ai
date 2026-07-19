"""organizations_b2b_tenancy

Revision ID: a8b9c0d1e2f3
Revises: f7a1b2c3d4e5
Create Date: 2026-06-15 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'f7a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS organization_members (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_role VARCHAR(50) NOT NULL DEFAULT 'viewer',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_org_members_org_user UNIQUE (organization_id, user_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS member_server_access (
            id SERIAL PRIMARY KEY,
            member_id INTEGER NOT NULL REFERENCES organization_members(id) ON DELETE CASCADE,
            server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
            CONSTRAINT uq_member_server_access UNIQUE (member_id, server_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS member_database_access (
            id SERIAL PRIMARY KEY,
            member_id INTEGER NOT NULL REFERENCES organization_members(id) ON DELETE CASCADE,
            server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
            database_name VARCHAR(255) NOT NULL,
            CONSTRAINT uq_member_database_access UNIQUE (member_id, server_id, database_name)
        )
    """)
    op.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE servers ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE restore_scenarios ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE cron_schedules ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE")


def downgrade() -> None:
    op.execute("ALTER TABLE cron_schedules DROP COLUMN IF EXISTS organization_id")
    op.execute("ALTER TABLE alert_rules DROP COLUMN IF EXISTS organization_id")
    op.execute("ALTER TABLE notification_channels DROP COLUMN IF EXISTS organization_id")
    op.execute("ALTER TABLE restore_scenarios DROP COLUMN IF EXISTS organization_id")
    op.execute("ALTER TABLE servers DROP COLUMN IF EXISTS organization_id")
    op.execute("ALTER TABLE audit_log DROP COLUMN IF EXISTS organization_id")
    op.execute("DROP TABLE IF EXISTS member_database_access")
    op.execute("DROP TABLE IF EXISTS member_server_access")
    op.execute("DROP TABLE IF EXISTS organization_members")
    op.execute("DROP TABLE IF EXISTS organizations")
