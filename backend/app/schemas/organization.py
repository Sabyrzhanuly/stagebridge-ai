from datetime import datetime
from pydantic import BaseModel


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberOut(BaseModel):
    id: int
    organization_id: int
    user_id: int
    username: str
    email: str
    org_role: str
    is_active: bool
    created_at: datetime
    # Сводка доступа для таблицы участников (без отдельного запроса на строку).
    all_servers: bool = False
    server_ids: list[int] = []


class MemberCreate(BaseModel):
    username: str
    email: str
    password: str
    org_role: str = "viewer"


class MemberUpdate(BaseModel):
    org_role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class MemberAccessOut(BaseModel):
    """Доступ конкретного участника к серверам/базам."""
    all_servers: bool
    server_ids: list[int]
    databases: list[dict]


class MemberAccessUpdate(BaseModel):
    server_ids: list[int] = []
    databases: list[dict] = []


class OrgPermissionOut(BaseModel):
    id: str
    label: str


class OrgRoleOut(BaseModel):
    role: str
    label: str
    all_servers: bool
    permissions: list[str]


class OrgRolesCatalogOut(BaseModel):
    permissions: list[OrgPermissionOut]
    roles: list[OrgRoleOut]
