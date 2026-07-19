"""structure_sync: partial unique index on active run per scenario

Revision ID: a1f4b7c2d9e3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1f4b7c2d9e3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE = "status IN ('queued', 'running', 'awaiting_approval')"


def upgrade() -> None:
    # Схлопываем существующие дубликаты активных прогонов на один сценарий:
    # оставляем самый свежий (max id), прочие переводим в failed — иначе
    # частичный уникальный индекс не создастся.
    op.execute(
        """
        UPDATE structure_sync_runs r
        SET status = 'failed',
            error_message = COALESCE(error_message,
                'Схлопнут дубликат активного прогона при миграции'),
            finished_at = COALESCE(finished_at, now())
        WHERE r.status IN ('queued', 'running', 'awaiting_approval')
          AND r.id <> (
              SELECT MAX(r2.id) FROM structure_sync_runs r2
              WHERE r2.scenario_id = r.scenario_id
                AND r2.status IN ('queued', 'running', 'awaiting_approval')
          )
        """
    )
    # Не более одного активного прогона на сценарий — закрывает гонку двойного
    # запуска на уровне БД (второй INSERT упадёт с IntegrityError → 409).
    op.create_index(
        "uq_structure_sync_active_run",
        "structure_sync_runs",
        ["scenario_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_structure_sync_active_run", table_name="structure_sync_runs")
