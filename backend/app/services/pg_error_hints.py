import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PgErrorHint:
    code: str
    title: str
    hint: str


_RULES: tuple[tuple[re.Pattern[str], PgErrorHint], ...] = (
    (
        re.compile(r"too many clients|53300|remaining connection slots", re.I),
        PgErrorHint(
            "too_many_clients",
            "Слишком много подключений",
            "Закройте idle-сессии (pg_stat_activity), проверьте утечки в приложениях "
            "или увеличьте max_connections. Долгосрочно — PgBouncer.",
        ),
    ),
    (
        re.compile(r"no space left on device|disk full|could not extend file|ENOSPC", re.I),
        PgErrorHint(
            "disk_full",
            "Недостаточно места на диске",
            "Освободите место на томе с data_directory PG (df -h), удалите старые WAL/логи, "
            "проверьте рост таблиц и pg_wal.",
        ),
    ),
    (
        re.compile(r"connection refused|could not connect to server|actively refused", re.I),
        PgErrorHint(
            "unreachable",
            "Сервер недоступен",
            "PostgreSQL не принимает соединения: проверьте, что служба запущена, "
            "порт и firewall, host/port в настройках сервера.",
        ),
    ),
    (
        re.compile(r"timeout|timed out|timeout expired", re.I),
        PgErrorHint(
            "timeout",
            "Таймаут подключения",
            "Сеть или PG не ответил вовремя: проверьте маршрут до хоста, нагрузку на сервер, "
            "pg_hba.conf и firewall.",
        ),
    ),
    (
        re.compile(r"password authentication failed|authentication failed|28P01", re.I),
        PgErrorHint(
            "auth_failed",
            "Ошибка аутентификации",
            "Неверный пароль или пользователь. Обновите учётные данные admin_user в карточке сервера.",
        ),
    ),
    (
        re.compile(r"no pg_hba\.conf entry|28000", re.I),
        PgErrorHint(
            "pg_hba",
            "Доступ запрещён (pg_hba)",
            "Добавьте запись в pg_hba.conf для IP Control Center / worker и перезагрузите конфиг PG.",
        ),
    ),
    (
        re.compile(r"database .+ does not exist|3D000", re.I),
        PgErrorHint(
            "database_missing",
            "База данных не найдена",
            "Указанная БД отсутствует на сервере или недоступна для подключения.",
        ),
    ),
    (
        re.compile(r"permission denied|42501", re.I),
        PgErrorHint(
            "permission_denied",
            "Недостаточно прав",
            "У admin_user не хватает прав для операции. Проверьте роль суперпользователя или GRANT.",
        ),
    ),
    (
        re.compile(r"could not translate host|name or service not known|getaddrinfo", re.I),
        PgErrorHint(
            "dns_error",
            "Хост не найден",
            "DNS не разрешает имя хоста. Проверьте host в настройках сервера.",
        ),
    ),
)

_DEFAULT = PgErrorHint(
    "generic",
    "Ошибка PostgreSQL",
    "Проверьте доступность сервера, логи PostgreSQL и параметры подключения в Control Center.",
)


def classify_pg_error(error: str | None) -> PgErrorHint:
    if not error or not error.strip():
        return _DEFAULT
    text = error.strip()
    for pattern, hint in _RULES:
        if pattern.search(text):
            return hint
    return PgErrorHint(
        _DEFAULT.code,
        _DEFAULT.title,
        text[:400] if len(text) > 400 else text,
    )
