import datetime

from sqlalchemy import String, Boolean, Integer, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MinioConfig(Base):
    """Каталог S3/MinIO хранилищ организации."""

    __tablename__ = "minio_config"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_minio_config_org_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    endpoint: Mapped[str] = mapped_column(String(255))
    access_key: Mapped[str] = mapped_column(String(255))
    secret_key: Mapped[str] = mapped_column(String(255))
    bucket: Mapped[str] = mapped_column(String(255))
    secure: Mapped[bool] = mapped_column(Boolean, default=False)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sign_version: Mapped[str] = mapped_column(String(8), default="v4")
    api_type: Mapped[str] = mapped_column(String(8), default="s3")
    swift_project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    swift_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
