from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import monitor_service
from app.schemas.monitoring import MonitoringSnapshot
from app.services.tenancy_service import get_owned_server
from app.api.deps import get_auth_context, AuthContext

router = APIRouter(
    prefix="/servers/{server_id}/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(get_auth_context)],
)


@router.get("", response_model=MonitoringSnapshot)
async def get_monitoring(
    server_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db)
    return await monitor_service.get_monitoring_for_api(server, refresh=refresh)
