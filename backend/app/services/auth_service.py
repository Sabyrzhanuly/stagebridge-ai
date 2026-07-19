import datetime
from typing import Any

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def _jwt_secret() -> str:
    """Секрет подписи JWT — отдельный от FERNET_KEY. Fail-fast, если не задан
    или оставлен плейсхолдер (иначе токены подписывались бы известным ключом)."""
    secret = settings.jwt_secret
    if not secret or len(secret) < 32 or secret == "your-jwt-secret-here":
        raise RuntimeError(
            "JWT_SECRET не задан (или короче 32 символов). Сгенерируйте: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return secret

PLATFORM_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "manage_servers", "manage_roles", "run_backup",
        "run_restore", "dangerous_ops", "view_all",
        "manage_users", "view_audit",
        "manage_scenarios", "manage_notifications", "manage_members",
        "view_servers",
    },
}

# Три плоские роли (RBAC 0/1). Права роли фиксированы в коде и назначаются
# человеку, а доступ к серверам/базам — это отдельная ось (per-user scope,
# см. MemberServerAccess), не зашитая в роль.
ORG_ROLE_PERMISSIONS: dict[str, set[str]] = {
    # Администратор — всё в организации, включая команду и уведомления.
    "org_admin": {
        "view_servers", "manage_servers", "manage_roles", "run_backup",
        "run_restore", "dangerous_ops", "view_audit",
        "manage_scenarios", "manage_notifications", "manage_members",
    },
    # Оператор — всё оперативное. Без разрушительных операций (DROP БД),
    # без управления участниками и каналами уведомлений.
    "operator": {
        "view_servers", "manage_servers", "manage_roles", "run_backup",
        "run_restore", "manage_scenarios", "view_audit",
    },
    # Наблюдатель — только чтение серверов и журнала аудита.
    "viewer": {
        "view_servers", "view_audit",
    },
}

# Только Администратор автоматически видит все серверы организации.
# Оператору и Наблюдателю доступ выдаётся явным списком per-user.
ORG_ROLES_WITH_ALL_SERVERS = frozenset({"org_admin"})

ORG_ROLE_LABELS: dict[str, str] = {
    "org_admin": "Администратор",
    "operator": "Оператор",
    "viewer": "Наблюдатель",
}

PERMISSION_LABELS: dict[str, str] = {
    "view_servers": "Просмотр серверов и баз",
    "manage_servers": "Добавление и настройка серверов PG",
    "manage_roles": "Роли и учётные записи PostgreSQL",
    "run_backup": "Создание и скачивание бэкапов",
    "run_restore": "Восстановление из бэкапа",
    "dangerous_ops": "Опасные операции (DROP БД и т.п.)",
    "view_audit": "Просмотр журнала аудита",
    "manage_scenarios": "Сценарии восстановления",
    "manage_notifications": "Каналы и правила уведомлений",
    "manage_members": "Управление участниками команды",
}


def org_roles_catalog() -> dict:
    all_perm_ids = sorted(
        {p for perms in ORG_ROLE_PERMISSIONS.values() for p in perms},
        key=lambda pid: PERMISSION_LABELS.get(pid, pid),
    )
    permissions = [
        {"id": pid, "label": PERMISSION_LABELS.get(pid, pid)}
        for pid in all_perm_ids
    ]
    roles = []
    for role in sorted(ORG_ROLE_PERMISSIONS.keys(), key=lambda r: ORG_ROLE_LABELS.get(r, r)):
        roles.append({
            "role": role,
            "label": ORG_ROLE_LABELS.get(role, role),
            "all_servers": role in ORG_ROLES_WITH_ALL_SERVERS,
            "permissions": sorted(
                ORG_ROLE_PERMISSIONS[role],
                key=lambda pid: PERMISSION_LABELS.get(pid, pid),
            ),
        })
    return {"permissions": permissions, "roles": roles}


PASSWORD_MIN_LENGTH = 8


def password_policy_error(password: str) -> str | None:
    """Проверка политики пароля. Возвращает текст ошибки или None, если ок.
    Чистая функция (без FastAPI) — вызывающий сам поднимает HTTPException(400).
    Требования: минимум 8 символов, хотя бы одна буква и одна цифра."""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов"
    if not any(c.isalpha() for c in password):
        return "Пароль должен содержать хотя бы одну букву"
    if not any(c.isdigit() for c in password):
        return "Пароль должен содержать хотя бы одну цифру"
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(
    user_id: int,
    role: str,
    *,
    org_id: int | None = None,
    org_role: str | None = None,
    member_id: int | None = None,
) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if org_id is not None:
        payload["org_id"] = org_id
    if org_role is not None:
        payload["org_role"] = org_role
    if member_id is not None:
        payload["member_id"] = member_id
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])


def is_platform_admin(role: str) -> bool:
    return role == "admin"


def has_platform_permission(role: str, permission: str) -> bool:
    return permission in PLATFORM_ROLE_PERMISSIONS.get(role, set())


def has_org_permission(org_role: str, permission: str) -> bool:
    return permission in ORG_ROLE_PERMISSIONS.get(org_role, set())


def effective_permissions(role: str, org_role: str | None) -> set[str]:
    if is_platform_admin(role):
        return PLATFORM_ROLE_PERMISSIONS["admin"]
    if org_role:
        return ORG_ROLE_PERMISSIONS.get(org_role, set())
    return set()


def has_permission(role: str, permission: str, org_role: str | None = None) -> bool:
    if is_platform_admin(role):
        return has_platform_permission(role, permission)
    if org_role:
        return has_org_permission(org_role, permission)
    return False
