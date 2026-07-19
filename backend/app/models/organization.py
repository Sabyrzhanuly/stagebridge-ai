import datetime
import re

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def slugify(name: str) -> str:
  s = name.strip().lower()
  s = re.sub(r"[^a-z0-9]+", "-", s)
  s = s.strip("-")
  return s[:80] or "org"


class Organization(Base):
  __tablename__ = "organizations"

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(255))
  slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
  created_at: Mapped[datetime.datetime] = mapped_column(
    DateTime, default=datetime.datetime.utcnow
  )


class OrganizationMember(Base):
  __tablename__ = "organization_members"
  __table_args__ = (
    UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  organization_id: Mapped[int] = mapped_column(
    ForeignKey("organizations.id", ondelete="CASCADE"), index=True
  )
  user_id: Mapped[int] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), index=True
  )
  org_role: Mapped[str] = mapped_column(String(50), default="viewer")
  is_active: Mapped[bool] = mapped_column(Boolean, default=True)
  created_at: Mapped[datetime.datetime] = mapped_column(
    DateTime, default=datetime.datetime.utcnow
  )


class MemberServerAccess(Base):
  """Доступ конкретного участника к серверу (per-user scope, не per-role)."""
  __tablename__ = "member_server_access"
  __table_args__ = (
    UniqueConstraint(
      "member_id", "server_id",
      name="uq_member_server_access",
    ),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  member_id: Mapped[int] = mapped_column(
    ForeignKey("organization_members.id", ondelete="CASCADE"), index=True
  )
  server_id: Mapped[int] = mapped_column(
    ForeignKey("servers.id", ondelete="CASCADE"), index=True
  )


class MemberDatabaseAccess(Base):
  """Ограничение доступа участника до конкретных баз сервера (пусто = все базы)."""
  __tablename__ = "member_database_access"
  __table_args__ = (
    UniqueConstraint(
      "member_id", "server_id", "database_name",
      name="uq_member_database_access",
    ),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  member_id: Mapped[int] = mapped_column(
    ForeignKey("organization_members.id", ondelete="CASCADE"), index=True
  )
  server_id: Mapped[int] = mapped_column(
    ForeignKey("servers.id", ondelete="CASCADE"), index=True
  )
  database_name: Mapped[str] = mapped_column(String(255))
