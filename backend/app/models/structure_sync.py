import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StructureSyncScenario(Base):
    """Сценарий аддитивной миграции структуры (structure_sync).

    prod → копия в temp → накат новой структуры из test → данные новых таблиц →
    проверка → свап имён (temp → target, старый target → to_delete__…).
    Ничего на бою не удаляется (аддитивно).
    """

    __tablename__ = "structure_sync_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))

    # Бой — источник полной копии (структура + данные)
    prod_server_id: Mapped[int] = mapped_column(Integer, index=True)
    prod_database: Mapped[str] = mapped_column(String(255))

    # Тест — источник новой структуры и данных новых таблиц
    test_server_id: Mapped[int] = mapped_column(Integer, index=True)
    test_database: Mapped[str] = mapped_column(String(255))

    # Приёмник — сервер, ГДЕ собирается новая БД (temp) и происходит свап.
    # Прод при этом ТОЛЬКО читается (pg_dump), ничего на нём не меняется.
    # Для старых сценариев миграция проставляет = prod_server_id (без смены поведения).
    target_server_id: Mapped[int] = mapped_column(Integer, index=True)

    # Финальное имя БД (обычно = prod_database). temp собирается и переименовывается в него.
    target_name: Mapped[str] = mapped_column(String(255))
    temp_name_template: Mapped[str] = mapped_column(
        String(255), default="{target}_build_{ts}"
    )

    # Префикс для отправленной «на удаление» старой БД и сколько прошлых хранить.
    old_db_prefix: Mapped[str] = mapped_column(String(100), default="to_delete__")
    keep_old_count: Mapped[int] = mapped_column(Integer, default=0)

    # new_tables_only | none
    data_copy_mode: Mapped[str] = mapped_column(String(50), default="new_tables_only")

    # JSON-список таблиц, у которых при клоне prod исключаются данные
    # (pg_dump --exclude-table-data): структура сохраняется, гигантские
    # данные (напр. логи ошибок) не тащатся. Пример: ["wpp.wpp_send_error_tab"].
    excluded_tables_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")

    require_approval: Mapped[bool] = mapped_column(Boolean, default=True)

    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    rowversion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class StructureSyncRun(Base):
    __tablename__ = "structure_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(Integer, index=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # running | awaiting_approval | success | failed | dry_run
    status: Mapped[str] = mapped_column(String(50), default="running")
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    temp_db: Mapped[str | None] = mapped_column(String(255), nullable=True)
    renamed_prod_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dropped_old_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")

    # Сгенерированный SQL (для dry_run/предпросмотра) и сводка по объектам.
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    rowversion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
