from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.pg_config_service import get_pg_config
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_owned_server
from app.schemas.pg_config import PgConfigSnapshot
from app.api.deps import get_auth_context, AuthContext

router = APIRouter(
    prefix="/servers/{server_id}/pg-config",
    tags=["pg-config"],
    dependencies=[Depends(get_auth_context)],
)


@router.get("", response_model=PgConfigSnapshot)
async def read_pg_config(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db)
    snapshot = await get_pg_config(server)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="server",
        entity_id=server_id,
        payload={"operation": "pg_config"},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return snapshot
