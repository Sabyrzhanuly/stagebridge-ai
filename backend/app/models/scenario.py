import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RestoreScenario(Base):
    __tablename__ = "restore_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))

    source_server_id: Mapped[int] = mapped_column(Integer, index=True)
    source_database: Mapped[str] = mapped_column(String(255))

    target_server_id: Mapped[int] = mapped_column(Integer, index=True)
    target_database: Mapped[str] = mapped_column(String(255))

    # drop | rename  (rename → target_database_old_YYYYMMDD_HHMMSS)
    old_db_action: Mapped[str] = mapped_column(String(50), default="drop")

    # JSON-список таблиц, исключённых из pg_dump: ["public.logs", "public.events"]
    excluded_tables_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")

    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Дамп, оставленный от НЕудачного прогона, чтобы при повторе не снимать заново
    # (может быть час+). Заполняется при провале, очищается при успехе.
    reuse_dump_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    reuse_dump_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reuse_dump_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    @property
    def reuse_dump_available(self) -> bool:
        return bool(self.reuse_dump_path)
    rowversion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class RestoreScenarioRun(Base):
    __tablename__ = "restore_scenario_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(Integer, index=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # running | success | failed
    status: Mapped[str] = mapped_column(String(50), default="running")
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    backup_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    renamed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    rowversion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
