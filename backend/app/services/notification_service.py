import json
from dataclasses import dataclass

import httpx
import aiosmtplib
from email.message import EmailMessage

from app.config import settings
from app.services.smtp_settings_service import SmtpConfig


@dataclass
class SendResult:
    ok: bool
    message: str = ""


async def send_telegram(chat_id: str, token: str, message: str) -> SendResult:
    if not token:
        return SendResult(False, "Bot token не указан")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=30.0,
            )
        if resp.status_code == 200:
            return SendResult(True, "Отправлено")
        return SendResult(False, f"Telegram API: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        return SendResult(False, str(e))


async def send_email(to: str, subject: str, body: str, smtp: SmtpConfig) -> SendResult:
    if not to:
        return SendResult(False, "Email получателя не указан")
    if not smtp.host:
        return SendResult(False, "SMTP сервер не настроен")

    msg = EmailMessage()
    msg["From"] = smtp.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if smtp.port == 465:
            await aiosmtplib.send(
                msg,
                hostname=smtp.host,
                port=smtp.port,
                username=smtp.user or None,
                password=smtp.password or None,
                use_tls=True,
            )
        else:
            await aiosmtplib.send(
                msg,
                hostname=smtp.host,
                port=smtp.port,
                username=smtp.user or None,
                password=smtp.password or None,
                start_tls=smtp.use_tls,
            )
        return SendResult(True, "Отправлено")
    except Exception as e:
        return SendResult(False, str(e))


async def send_notification(
    channel_type: str,
    config_json: str,
    message: str,
    *,
    smtp: SmtpConfig | None = None,
) -> SendResult:
    config = json.loads(config_json)
    if channel_type == "telegram":
        return await send_telegram(
            config.get("chat_id", settings.telegram_chat_id),
            config.get("bot_token", settings.telegram_bot_token),
            message,
        )
    if channel_type == "email":
        # SMTP уже вычислен вызывающим и передан аргументом `smtp`
        # (smtp_settings_service.smtp_from_channel_config). Не пересчитываем.
        if smtp is None:
            return SendResult(False, "SMTP не настроен в канале")
        return await send_email(
            config.get("to", ""),
            config.get("subject", "PG Control Center"),
            message,
            smtp,
        )
    return SendResult(False, f"Неизвестный тип канала: {channel_type}")
