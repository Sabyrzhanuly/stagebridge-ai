from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.database import get_db
from app.models.minio_config import MinioConfig
from app.models.server import Server
from app.schemas.s3_storage import (
    S3StorageCreate,
    S3StorageUpdate,
    S3StorageOut,
    S3StorageTestRequest,
    ServerStorageAssign,
)
from app.services import minio_service
from app.services.minio_service import normalize_storage_endpoint, normalize_api_type
from app.services.audit_service import audit_action
from app.api.deps import get_auth_context, AuthContext, RequirePermission

router = APIRouter(prefix="/s3-storages", tags=["s3-storages"])


def _require_org(auth: AuthContext) -> int:
    if auth.org is None:
        raise HTTPException(403, "Доступно только участникам организации")
    return auth.org.organization_id


async def _get_org_storage(storage_id: int, auth: AuthContext, db: AsyncSession) -> MinioConfig:
    row = await db.get(MinioConfig, storage_id)
    if not row:
        raise HTTPException(404, "Хранилище не найдено")
    if row.organization_id != _require_org(auth):
        raise HTTPException(403, "Нет доступа к этому хранилищу")
    return row


@router.get("", response_model=list[S3StorageOut])
async def list_s3_storages(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    org_id = _require_org(auth)
    result = await db.execute(
        select(MinioConfig)
        .where(MinioConfig.organization_id == org_id)
        .order_by(MinioConfig.name)
    )
    return result.scalars().all()


@router.post("", response_model=S3StorageOut, status_code=201)
async def create_s3_storage(
    data: S3StorageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    org_id = _require_org(auth)
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Укажите название хранилища")
    existing = await db.execute(
        select(MinioConfig.id).where(
            MinioConfig.organization_id == org_id,
            MinioConfig.name == name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "Хранилище с таким названием уже есть")

    api_type = normalize_api_type(data.api_type)
    endpoint, secure = normalize_storage_endpoint(api_type, data.endpoint.strip(), data.secure)
    row = MinioConfig(
        organization_id=org_id,
        name=name,
        endpoint=endpoint,
        access_key=data.access_key,
        secret_key=data.secret_key,
        bucket=data.bucket.strip(),
        secure=secure,
        region=data.region,
        sign_version=data.sign_version,
        api_type=api_type,
        swift_project=data.swift_project,
        swift_domain=data.swift_domain,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="s3_storage",
        entity_id=row.id,
        payload={"name": row.name, "endpoint": row.endpoint, "bucket": row.bucket},
        organization_id=org_id,
    )
    return row


@router.put("/{storage_id}", response_model=S3StorageOut)
async def update_s3_storage(
    storage_id: int,
    data: S3StorageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    row = await _get_org_storage(storage_id, auth, db)
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(400, "Укажите название хранилища")
        dup = await db.execute(
            select(MinioConfig.id).where(
                MinioConfig.organization_id == row.organization_id,
                MinioConfig.name == name,
                MinioConfig.id != storage_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(409, "Хранилище с таким названием уже есть")
        row.name = name
    if data.endpoint is not None:
        endpoint = data.endpoint.strip()
        secure = data.secure if data.secure is not None else row.secure
        api_type = normalize_api_type(data.api_type or row.api_type)
        row.endpoint, row.secure = normalize_storage_endpoint(api_type, endpoint, secure)
    elif data.secure is not None:
        row.secure = data.secure
    if data.api_type is not None:
        row.api_type = normalize_api_type(data.api_type)
    if data.access_key is not None:
        row.access_key = data.access_key
    if data.secret_key is not None:
        row.secret_key = data.secret_key
    if data.bucket is not None:
        row.bucket = data.bucket.strip()
    if data.region is not None:
        row.region = data.region
    if data.sign_version is not None:
        row.sign_version = data.sign_version
    if data.swift_project is not None:
        row.swift_project = data.swift_project
    if data.swift_domain is not None:
        row.swift_domain = data.swift_domain
    await db.commit()
    await db.refresh(row)
    minio_service.invalidate_cache(storage_id)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="s3_storage",
        entity_id=row.id,
        payload=data.model_dump(exclude_unset=True, exclude={"secret_key"}),
        organization_id=row.organization_id,
    )
    return row


@router.delete("/{storage_id}", status_code=204)
async def delete_s3_storage(
    storage_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    row = await _get_org_storage(storage_id, auth, db)
    in_use = await db.execute(
        select(Server.id).where(Server.storage_id == storage_id).limit(1)
    )
    if in_use.scalar_one_or_none() is not None:
        raise HTTPException(409, "Хранилище привязано к серверам — сначала отвяжите")
    await db.delete(row)
    await db.commit()
    minio_service.invalidate_cache(storage_id)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="s3_storage",
        entity_id=storage_id,
        payload={"name": row.name},
        organization_id=row.organization_id,
    )


@router.post("/{storage_id}/test")
async def test_s3_storage(
    storage_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    row = await _get_org_storage(storage_id, auth, db)
    return minio_service.test_connection(
        endpoint=row.endpoint,
        access_key=row.access_key,
        secret_key=row.secret_key,
        bucket=row.bucket,
        secure=row.secure,
        region=row.region,
        sign_version=row.sign_version,
        api_type=row.api_type,
        swift_project=row.swift_project,
        swift_domain=row.swift_domain,
    )


@router.post("/test")
async def test_s3_storage_payload(
    data: S3StorageTestRequest,
    _: AuthContext = Depends(get_auth_context),
    __=Depends(RequirePermission("run_backup")),
):
    return minio_service.test_connection(
        endpoint=data.endpoint,
        access_key=data.access_key,
        secret_key=data.secret_key,
        bucket=data.bucket,
        secure=data.secure,
        region=data.region,
        sign_version=data.sign_version,
        api_type=data.api_type,
        swift_project=data.swift_project,
        swift_domain=data.swift_domain,
    )
