import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CronSchedule(Base):
    __tablename__ = "cron_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    cron_expression: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    rowversion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


DEFAULT_SCHEDULES = [
    ("Каждый час",                    "0 * * * *",   "В начале каждого часа"),
    ("Каждые 2 часа",                 "0 */2 * * *", "Раз в 2 часа начиная с полуночи"),
    ("Каждый день в полночь",         "0 0 * * *",   "00:00 UTC ежедневно"),
    ("Каждый день в 01:00",           "0 1 * * *",   "Ночью, минимальная нагрузка"),
    ("Каждый день в 02:00",           "0 2 * * *",   ""),
    ("Каждый день в 03:00",           "0 3 * * *",   "Стандартное ночное расписание"),
    ("Каждый день в 06:00",           "0 6 * * *",   "Раннее утро"),
    ("Дважды в день (06:00 и 18:00)", "0 6,18 * * *",""),
    ("Каждое воскресенье в 03:00",    "0 3 * * 0",   "Еженедельный бэкап"),
    ("Каждый понедельник в 06:00",    "0 6 * * 1",   ""),
    ("Каждую пятницу в 22:00",        "0 22 * * 5",  "Перед выходными"),
    ("1-е число каждого месяца 03:00","0 3 1 * *",   "Ежемесячный бэкап"),
]
