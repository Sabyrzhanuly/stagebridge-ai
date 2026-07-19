from pydantic import BaseModel


class RoleOut(BaseModel):
    rolname: str
    rolcanlogin: bool
    rolsuper: bool
    rolinherit: bool
    rolcreatedb: bool
    rolcreaterole: bool
    rolconnlimit: int
    member_of: list[str]


class RoleCreate(BaseModel):
    username: str
    password: str | None = None
    group: str = "app_users"


class ServiceAccountCreate(BaseModel):
    username: str
    password: str | None = None
    database: str


class RoleGrantRevoke(BaseModel):
    group: str
