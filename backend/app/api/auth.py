from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, slugify
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest,
    UserOut, UserCreate, UserUpdate, RegisterRequest,
    UserMeOut, OrganizationOut,
)
from app.services.auth_service import (
    verify_password, hash_password, password_policy_error,
    create_access_token, create_refresh_token, decode_token,
    effective_permissions, is_platform_admin, ORG_ROLE_PERMISSIONS,
    has_platform_permission,
)
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_primary_membership
from app.config import settings
from app.api.deps import get_current_user, get_auth_context, RequirePermission, AuthContext

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Rate-limit логина (анти-брутфорс) через Redis ──
import redis.asyncio as _aioredis

_LOGIN_MAX = 10        # неудачных попыток
_LOGIN_WINDOW = 900    # за окно, сек (15 мин)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _login_guard(request: Request, username: str):
    """Возвращает redis-клиент; при превышении лимита по IP или логину — 429.
    Redis недоступен → fail-open (не блокируем логин), чтобы не положить вход."""
    r = _aioredis.from_url(settings.redis_url)
    ip = _client_ip(request)
    for key in (f"login_fail:ip:{ip}", f"login_fail:user:{username}"):
        try:
            n = await r.get(key)
        except Exception:  # noqa: BLE001
            return r
        if n is not None and int(n) >= _LOGIN_MAX:
            try:
                await r.aclose()
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(
                429, "Слишком много попыток входа. Повторите позже.",
                headers={"Retry-After": str(_LOGIN_WINDOW)},
            )
    return r


async def _login_fail(r, request: Request, username: str) -> None:
    ip = _client_ip(request)
    try:
        async with r.pipeline() as pipe:
            for key in (f"login_fail:ip:{ip}", f"login_fail:user:{username}"):
                pipe.incr(key)
                pipe.expire(key, _LOGIN_WINDOW)
            await pipe.execute()
    except Exception:  # noqa: BLE001
        pass


async def _login_ok(r, request: Request, username: str) -> None:
    ip = _client_ip(request)
    try:
        await r.delete(f"login_fail:ip:{ip}", f"login_fail:user:{username}")
    except Exception:  # noqa: BLE001
        pass


async def _issue_tokens(user: User, db: AsyncSession) -> TokenResponse:
    if is_platform_admin(user.role):
        return TokenResponse(
            access_token=create_access_token(user.id, user.role),
            refresh_token=create_refresh_token(user.id),
        )
    member = await get_primary_membership(user, db)
    if not member:
        raise HTTPException(403, "Пользователь не состоит ни в одной организации")
    org = await db.get(Organization, member.organization_id)
    if not org:
        raise HTTPException(403, "Организация не найдена")
    return TokenResponse(
        access_token=create_access_token(
            user.id,
            user.role,
            org_id=org.id,
            org_role=member.org_role,
            member_id=member.id,
        ),
        refresh_token=create_refresh_token(user.id),
    )


async def _build_me(user: User, db: AsyncSession) -> UserMeOut:
    perms = sorted(effective_permissions(user.role, None))
    org_out = None
    org_role = None
    member_id = None
    if not is_platform_admin(user.role):
        member = await get_primary_membership(user, db)
        if member:
            org = await db.get(Organization, member.organization_id)
            if org:
                org_out = OrganizationOut.model_validate(org)
            org_role = member.org_role
            member_id = member.id
            perms = sorted(effective_permissions(user.role, member.org_role))
    return UserMeOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        is_super_admin=is_platform_admin(user.role),
        organization=org_out,
        org_role=org_role,
        member_id=member_id,
        permissions=perms,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(403, "Регистрация отключена")

    username = body.username.strip()
    email = body.email.strip().lower()
    company_name = body.company_name.strip()
    if len(username) < 3:
        raise HTTPException(400, "Логин не короче 3 символов")
    if err := password_policy_error(body.password):
        raise HTTPException(400, err)
    if len(company_name) < 2:
        raise HTTPException(400, "Название компании не короче 2 символов")

    exists = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(409, "Пользователь с таким логином или email уже существует")

    base_slug = slugify(company_name)
    slug = base_slug
    n = 1
    while True:
        dup = await db.execute(select(Organization).where(Organization.slug == slug))
        if not dup.scalar_one_or_none():
            break
        n += 1
        slug = f"{base_slug}-{n}"

    org = Organization(name=company_name, slug=slug)
    db.add(org)
    await db.flush()

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(body.password),
        role="user",
    )
    db.add(user)
    await db.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        org_role="org_admin",
    )
    db.add(member)
    await db.commit()
    await db.refresh(user)

    await audit_action(
        db,
        user=user,
        request=request,
        action="create",
        entity_type="organization",
        entity_id=org.id,
        payload={"name": org.name, "username": user.username, "source": "register"},
        organization_id=org.id,
    )

    from app.tasks.queues import register_org_queue
    register_org_queue(org.id)

    return TokenResponse(
        access_token=create_access_token(
            user.id, user.role, org_id=org.id, org_role=member.org_role, member_id=member.id
        ),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    r = await _login_guard(request, body.username)  # 429 при брутфорсе
    try:
        result = await db.execute(
            select(User).where(User.username == body.username)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(body.password, user.password_hash):
            await _login_fail(r, request, body.username)
            await audit_action(
                db,
                user=None,
                request=request,
                action="login",
                entity_type="user",
                payload={"username": body.username},
                result="failed",
                username=body.username,
            )
            raise HTTPException(401, "Неверный логин или пароль")
        if not user.is_active:
            await audit_action(
                db,
                user=user,
                request=request,
                action="login",
                entity_type="user",
                entity_id=user.id,
                result="failed",
                payload={"reason": "inactive"},
            )
            raise HTTPException(403, "Пользователь деактивирован")

        tokens = await _issue_tokens(user, db)
        await _login_ok(r, request, body.username)  # сброс счётчиков после успеха
        member = await get_primary_membership(user, db)
        await audit_action(
            db,
            user=user,
            request=request,
            action="login",
            entity_type="user",
            entity_id=user.id,
            organization_id=member.organization_id if member else None,
        )
        return tokens
    finally:
        try:
            await r.aclose()
        except Exception:  # noqa: BLE001
            pass


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Неверный тип токена")
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Невалидный refresh-токен")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Пользователь не найден")

    return await _issue_tokens(user, db)


@router.get("/me", response_model=UserMeOut)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _build_me(user, db)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_users")),
):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(RequirePermission("manage_users")),
):
    exists = await db.execute(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(409, "Пользователь с таким username или email уже существует")

    valid_roles = {"admin", "user"}
    if body.role not in valid_roles:
        raise HTTPException(400, f"Роль должна быть одной из: {', '.join(sorted(valid_roles))}")
    if err := password_policy_error(body.password):
        raise HTTPException(400, err)

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await audit_action(
        db,
        user=actor,
        request=request,
        action="create",
        entity_type="user",
        entity_id=user.id,
        payload={"username": user.username, "role": user.role},
    )
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(RequirePermission("manage_users")),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "password" and value is not None:
            if err := password_policy_error(value):
                raise HTTPException(400, err)
            user.password_hash = hash_password(value)
        elif field != "password":
            setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    await audit_action(
        db,
        user=actor,
        request=request,
        action="update",
        entity_type="user",
        entity_id=user.id,
        payload=body.model_dump(exclude_unset=True),
    )
    return user
