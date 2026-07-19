from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.models.organization_smtp import OrganizationSmtp
from app.services.crypto import decrypt, encrypt


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    mail_from: str
    use_tls: bool
    source: str  # db | env


DOMAIN_PRESETS: dict[str, dict] = {
    "gmail.com": {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    "googlemail.com": {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    "yandex.ru": {"host": "smtp.yandex.ru", "port": 465, "use_tls": True},
    "yandex.com": {"host": "smtp.yandex.com", "port": 465, "use_tls": True},
    "ya.ru": {"host": "smtp.yandex.ru", "port": 465, "use_tls": True},
    "mail.ru": {"host": "smtp.mail.ru", "port": 465, "use_tls": True},
    "bk.ru": {"host": "smtp.mail.ru", "port": 465, "use_tls": True},
    "inbox.ru": {"host": "smtp.mail.ru", "port": 465, "use_tls": True},
    "list.ru": {"host": "smtp.mail.ru", "port": 465, "use_tls": True},
    "outlook.com": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "hotmail.com": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "live.com": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "icloud.com": {"host": "smtp.mail.me.com", "port": 587, "use_tls": True},
    "me.com": {"host": "smtp.mail.me.com", "port": 587, "use_tls": True},
}


def detect_from_email(email: str) -> dict:
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Укажите корректный email")
    domain = email.split("@", 1)[1]
    preset = DOMAIN_PRESETS.get(domain)
    if not preset:
        raise ValueError(
            f"Автоопределение для домена «{domain}» недоступно. "
            "Укажите SMTP host и port вручную."
        )
    return {
        "smtp_host": preset["host"],
        "smtp_port": preset["port"],
        "smtp_user": email,
        "smtp_from": email,
        "use_tls": preset["use_tls"],
        "detected_domain": domain,
    }


def sanitize_email_channel_config(config: dict) -> dict:
    """Убирает секреты из конфига для ответа API."""
    return {
        "to": config.get("to", ""),
        "smtp_host": config.get("smtp_host", ""),
        "smtp_port": config.get("smtp_port", 587),
        "smtp_user": config.get("smtp_user", ""),
        "smtp_from": config.get("smtp_from", ""),
        "use_tls": config.get("use_tls", True),
        "subject": config.get("subject", "PG Control Center"),
        "has_smtp_password": bool(config.get("smtp_password_encrypted")),
    }


def smtp_from_channel_config(config: dict) -> SmtpConfig | None:
    host = (config.get("smtp_host") or "").strip()
    if not host:
        return None
    password = ""
    encrypted = config.get("smtp_password_encrypted")
    if encrypted:
        try:
            password = decrypt(encrypted)
        except Exception:
            password = ""
    smtp_user = (config.get("smtp_user") or "").strip()
    smtp_from = (config.get("smtp_from") or smtp_user or "").strip()
    port = config.get("smtp_port", 587)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 587
    return SmtpConfig(
        host=host,
        port=port,
        user=smtp_user,
        password=password,
        mail_from=smtp_from,
        use_tls=bool(config.get("use_tls", True)),
        source="channel",
    )


def prepare_email_channel_config(config: dict, existing: dict | None = None) -> dict:
    to = (config.get("to") or "").strip()
    if not to:
        raise ValueError("Укажите email получателя")

    smtp_host = (config.get("smtp_host") or "").strip()
    if not smtp_host:
        raise ValueError("Укажите SMTP host")

    smtp_port = config.get("smtp_port", 587)
    try:
        smtp_port = int(smtp_port)
    except (TypeError, ValueError):
        raise ValueError("Некорректный SMTP port")
    if smtp_port < 1 or smtp_port > 65535:
        raise ValueError("Некорректный SMTP port")

    smtp_user = (config.get("smtp_user") or "").strip()
    if not smtp_user:
        raise ValueError("Укажите SMTP логин")

    smtp_from = (config.get("smtp_from") or smtp_user).strip()
    use_tls = bool(config.get("use_tls", True))
    subject = (config.get("subject") or "PG Control Center").strip() or "PG Control Center"

    password_plain = config.get("smtp_password")
    if password_plain:
        password_encrypted = encrypt(password_plain)
    elif existing and existing.get("smtp_password_encrypted"):
        password_encrypted = existing["smtp_password_encrypted"]
    else:
        raise ValueError("Укажите пароль SMTP")

    return {
        "to": to,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_from": smtp_from,
        "use_tls": use_tls,
        "subject": subject,
        "smtp_password_encrypted": password_encrypted,
    }


def _env_smtp_config() -> SmtpConfig | None:
    if not settings.smtp_host:
        return None
    return SmtpConfig(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        mail_from=settings.smtp_from or settings.smtp_user or "pgadmin@localhost",
        use_tls=True,
        source="env",
    )


def _row_to_config(row: OrganizationSmtp) -> SmtpConfig:
    password = ""
    if row.smtp_password_encrypted:
        try:
            password = decrypt(row.smtp_password_encrypted)
        except Exception:
            password = ""
    return SmtpConfig(
        host=row.smtp_host,
        port=row.smtp_port,
        user=row.smtp_user,
        password=password,
        mail_from=row.smtp_from,
        use_tls=row.use_tls,
        source="db",
    )


async def get_smtp_config(db: AsyncSession, organization_id: int) -> SmtpConfig | None:
    result = await db.execute(
        select(OrganizationSmtp).where(OrganizationSmtp.organization_id == organization_id)
    )
    row = result.scalar_one_or_none()
    if row:
        return _row_to_config(row)
    return _env_smtp_config()


def get_smtp_config_sync(session: Session, organization_id: int) -> SmtpConfig | None:
    row = session.execute(
        select(OrganizationSmtp).where(OrganizationSmtp.organization_id == organization_id)
    ).scalar_one_or_none()
    if row:
        return _row_to_config(row)
    return _env_smtp_config()


async def is_configured(db: AsyncSession, organization_id: int) -> bool:
    cfg = await get_smtp_config(db, organization_id)
    return cfg is not None and bool(cfg.host)


async def get_smtp_status(db: AsyncSession, organization_id: int) -> dict:
    result = await db.execute(
        select(OrganizationSmtp).where(OrganizationSmtp.organization_id == organization_id)
    )
    row = result.scalar_one_or_none()
    env_cfg = _env_smtp_config()
    if row:
        return {
            "configured": True,
            "source": "db",
            "smtp_host": row.smtp_host,
            "smtp_port": row.smtp_port,
            "smtp_user": row.smtp_user,
            "smtp_from": row.smtp_from,
            "use_tls": row.use_tls,
            "has_password": bool(row.smtp_password_encrypted),
            "env_fallback": env_cfg is not None,
        }
    if env_cfg:
        return {
            "configured": True,
            "source": "env",
            "smtp_host": env_cfg.host,
            "smtp_port": env_cfg.port,
            "smtp_user": env_cfg.user,
            "smtp_from": env_cfg.mail_from,
            "use_tls": env_cfg.use_tls,
            "has_password": bool(env_cfg.password),
            "env_fallback": True,
        }
    return {
        "configured": False,
        "source": None,
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_from": "",
        "use_tls": True,
        "has_password": False,
        "env_fallback": False,
    }


async def save_smtp_settings(
    db: AsyncSession,
    organization_id: int,
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_from: str,
    use_tls: bool,
    smtp_password: str | None = None,
) -> OrganizationSmtp:
    if not smtp_host.strip():
        raise ValueError("Укажите SMTP host")
    if smtp_port < 1 or smtp_port > 65535:
        raise ValueError("Некорректный SMTP port")

    result = await db.execute(
        select(OrganizationSmtp).where(OrganizationSmtp.organization_id == organization_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        if not smtp_password:
            raise ValueError("Укажите пароль SMTP")
        row = OrganizationSmtp(organization_id=organization_id, smtp_password_encrypted="")
        db.add(row)

    row.smtp_host = smtp_host.strip()
    row.smtp_port = smtp_port
    row.smtp_user = smtp_user.strip()
    row.smtp_from = (smtp_from or smtp_user).strip()
    row.use_tls = use_tls
    if smtp_password:
        row.smtp_password_encrypted = encrypt(smtp_password)

    await db.commit()
    await db.refresh(row)
    return row
