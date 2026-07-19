import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AuditLog(Base):
  __tablename__ = "audit_log"

  id: Mapped[int] = mapped_column(primary_key=True)
  organization_id: Mapped[int | None] = mapped_column(
    ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
  )
  user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
  username: Mapped[str] = mapped_column(String(150), default="system")
  action: Mapped[str] = mapped_column(String(100), index=True)
  entity_type: Mapped[str] = mapped_column(String(100))
  entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
  payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
  result: Mapped[str] = mapped_column(String(50), default="success")
  ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
  created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True)
