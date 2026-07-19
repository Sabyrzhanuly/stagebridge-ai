import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PgClientCatalog(Base):
    __tablename__ = "pg_client_catalog"
    __table_args__ = (
        UniqueConstraint("major_version", name="uq_pg_client_catalog_major"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    major_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
