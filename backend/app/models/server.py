import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Server(Base):
    __tablename__ = "servers"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_servers_org_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=5432)
    admin_user: Mapped[str] = mapped_column(String(255), default="postgres")
    admin_password_encrypted: Mapped[str] = mapped_column(Text)
    ssh_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str] = mapped_column(String(50), default="dev")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    pg_major_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_id: Mapped[int | None] = mapped_column(
        ForeignKey("minio_config.id", ondelete="SET NULL"), nullable=True, index=True
    )
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    health_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_checked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    health_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
