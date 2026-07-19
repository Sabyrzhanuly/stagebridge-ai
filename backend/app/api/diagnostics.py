from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.diagnostic_service import run_diagnostics
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_owned_server
from app.schemas.diagnostic import DiagnosticReport
from app.api.deps import get_auth_context, AuthContext

router = APIRouter(
    prefix="/servers/{server_id}/diagnostics",
    tags=["diagnostics"],
    dependencies=[Depends(get_auth_context)],
)


@router.get("", response_model=DiagnosticReport)
async def get_diagnostics(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db)
    report = await run_diagnostics(server)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="server",
        entity_id=server_id,
        payload={"operation": "diagnostics"},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return report
