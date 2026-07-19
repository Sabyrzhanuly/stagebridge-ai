from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pg_client import PgClientCatalog
from app.models.server import Server
from app.services import pg_client_service


async def ensure_requested(db: AsyncSession, major: int) -> None:
    result = await db.execute(
        select(PgClientCatalog).where(PgClientCatalog.major_version == major)
    )
    if result.scalar_one_or_none() is None:
        db.add(PgClientCatalog(major_version=major, source="requested"))
        await db.commit()


async def add_manual(db: AsyncSession, major: int, note: str | None = None) -> PgClientCatalog:
    pg_client_service.validate_manual_major(major)
    result = await db.execute(
        select(PgClientCatalog).where(PgClientCatalog.major_version == major)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    row = PgClientCatalog(major_version=major, source="manual", note=note)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def remove_from_catalog(db: AsyncSession, major: int) -> None:
    if pg_client_service.is_installed(major):
        raise ValueError("Сначала удалите установленный клиент из контейнера")

    in_use = await db.execute(
        select(Server.id).where(Server.pg_major_version == major).limit(1)
    )
    if in_use.scalar_one_or_none() is not None:
        raise ValueError("Версия используется серверами — убрать из списка нельзя")

    result = await db.execute(
        select(PgClientCatalog).where(PgClientCatalog.major_version == major)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError("Версия не найдена в каталоге")
    await db.delete(row)
    await db.commit()


async def list_catalog_items(db: AsyncSession) -> list[dict]:
    catalog_result = await db.execute(
        select(PgClientCatalog).order_by(PgClientCatalog.major_version)
    )
    catalog_rows = catalog_result.scalars().all()

    servers_result = await db.execute(
        select(Server.pg_major_version, Server.name, Server.id)
        .where(Server.pg_major_version.isnot(None))
        .order_by(Server.pg_major_version, Server.name)
    )
    version_servers: dict[int, list[dict]] = {}
    for pg_ver, name, srv_id in servers_result.all():
        version_servers.setdefault(pg_ver, []).append({"id": srv_id, "name": name})

    items: list[dict] = []
    available = {p["major"]: p for p in pg_client_service.list_available_clients().get("packages", [])}
    for entry in catalog_rows:
        major = entry.major_version
        servers_list = version_servers.get(major, [])
        installed = pg_client_service.is_installed(major)
        apt_info = available.get(major)
        items.append({
            "id": entry.id,
            "major": major,
            "source": entry.source,
            "note": entry.note,
            "installed": installed,
            "available_in_repo": apt_info is not None,
            "candidate": apt_info.get("candidate") if apt_info else None,
            "bin_path": pg_client_service.bin_path(major),
            "servers": servers_list,
            "requested": len(servers_list) > 0,
        })
    return items
