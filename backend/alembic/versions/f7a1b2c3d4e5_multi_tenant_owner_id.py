"""multi_tenant_owner_id

Revision ID: f7a1b2c3d4e5
Revises: e6c3f8a2b104
Create Date: 2026-06-15 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'f7a1b2c3d4e5'
down_revision: Union[str, None] = 'e6c3f8a2b104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE servers ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute(
        "UPDATE servers SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_servers_owner_id ON servers(owner_id)")
    op.execute("ALTER TABLE servers DROP CONSTRAINT IF EXISTS uq_servers_name")
    op.execute(
        "ALTER TABLE servers ADD CONSTRAINT uq_servers_owner_name UNIQUE (owner_id, name)"
    )

    op.execute(
        "ALTER TABLE restore_scenarios ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute(
        "UPDATE restore_scenarios SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_restore_scenarios_owner_id ON restore_scenarios(owner_id)")

    op.execute(
        "ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute(
        "UPDATE notification_channels SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_notification_channels_owner_id ON notification_channels(owner_id)")
    op.execute("ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS uq_notification_channels_name")
    op.execute(
        "ALTER TABLE notification_channels ADD CONSTRAINT uq_notification_channels_owner_name UNIQUE (owner_id, name)"
    )

    op.execute(
        "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute(
        "UPDATE alert_rules SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_rules_owner_id ON alert_rules(owner_id)")

    op.execute(
        "ALTER TABLE cron_schedules ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_cron_schedules_owner_id ON cron_schedules(owner_id)")


def downgrade() -> None:
    op.execute("ALTER TABLE cron_schedules DROP COLUMN IF EXISTS owner_id")
    op.execute("ALTER TABLE alert_rules DROP COLUMN IF EXISTS owner_id")
    op.execute("ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS uq_notification_channels_owner_name")
    op.execute("ALTER TABLE notification_channels DROP COLUMN IF EXISTS owner_id")
    op.execute("ALTER TABLE restore_scenarios DROP COLUMN IF EXISTS owner_id")
    op.execute("ALTER TABLE servers DROP CONSTRAINT IF EXISTS uq_servers_owner_name")
    op.execute("ALTER TABLE servers DROP COLUMN IF EXISTS owner_id")
