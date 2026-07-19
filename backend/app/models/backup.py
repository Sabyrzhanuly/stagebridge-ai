import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BackupSchedule(Base):
    __tablename__ = "backup_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    database_name: Mapped[str] = mapped_column(String(255))
    cron_expression: Mapped[str] = mapped_column(String(100))
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    storage_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class BackupHistory(Base):
    __tablename__ = "backup_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    database_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    backup_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_id: Mapped[int | None] = mapped_column(
        ForeignKey("minio_config.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class RestoreHistory(Base):
    """История восстановлений — для аудита и взаимного исключения с бэкапами."""
    __tablename__ = "restore_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    database_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))  # running | success | failed
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Исходный бэкап, из которого восстанавливали (если известен).
    backup_id: Mapped[int | None] = mapped_column(
        ForeignKey("backup_history.id", ondelete="SET NULL"), nullable=True
    )
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    backup_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
