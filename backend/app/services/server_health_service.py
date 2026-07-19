from datetime import datetime

from app.models.server import Server
from app.services.crypto import decrypt
from app.services.pg_connection import test_connection
from app.services.pg_error_hints import classify_pg_error

HEALTH_ONLINE = "online"
HEALTH_DEGRADED = "degraded"
HEALTH_OFFLINE = "offline"
HEALTH_UNKNOWN = "unknown"

DEFAULT_OFFLINE_THRESHOLD = 3


async def probe_server_health(server: Server) -> tuple[bool, str | None, str | None, int | None]:
    try:
        password = decrypt(server.admin_password_encrypted)
    except Exception as exc:
        return False, None, f"Не удалось расшифровать пароль: {exc}", None
    return await test_connection(server.host, server.port, server.admin_user, password)


def apply_health_probe(
    server: Server,
    ok: bool,
    error: str | None,
    pg_major: int | None,
    *,
    offline_threshold: int = DEFAULT_OFFLINE_THRESHOLD,
) -> tuple[bool, bool]:
    """Обновляет поля health на server. Возвращает (стал_offline, восстановился)."""
    prev_status = server.health_status or HEALTH_UNKNOWN
    was_offline = prev_status == HEALTH_OFFLINE
    now = datetime.utcnow()
    server.health_checked_at = now

    if ok:
        server.health_status = HEALTH_ONLINE
        server.health_error = None
        server.health_fail_count = 0
        if pg_major is not None:
            server.pg_major_version = pg_major
        return False, was_offline

    server.health_fail_count = int(server.health_fail_count or 0) + 1
    server.health_error = error
    became_offline = False

    if server.health_fail_count >= offline_threshold:
        if prev_status != HEALTH_OFFLINE:
            became_offline = True
        server.health_status = HEALTH_OFFLINE
    else:
        server.health_status = HEALTH_DEGRADED

    return became_offline, False


def health_is_actionable(server: Server) -> bool:
    return (server.health_status or HEALTH_UNKNOWN) == HEALTH_ONLINE


def format_unreachable_message(server: Server) -> str:
    hint = classify_pg_error(server.health_error)
    fail_count = server.health_fail_count or 0
    return (
        f"🔴 <b>Сервер недоступен</b>\n"
        f"🖥 <code>{server.name}</code> ({server.host}:{server.port})\n"
        f"📋 {hint.title}\n"
        f"💡 {hint.hint}\n"
        f"Неудачных проверок подряд: {fail_count}"
    )


def format_recovered_message(server: Server) -> str:
    return (
        f"🟢 <b>Сервер снова доступен</b>\n"
        f"🖥 <code>{server.name}</code> ({server.host}:{server.port})"
    )
