from pydantic import BaseModel


class DatabaseOut(BaseModel):
    datname: str
    owner: str
    size: str
    size_bytes: int
    datacl: str | None
    encoding: str


class DatabaseCreate(BaseModel):
    name: str
    mode: str = "shared"
    with_service: bool = False


class SchemaOut(BaseModel):
    schema_name: str
    owner: str


class TableOut(BaseModel):
    schema_name: str
    table_name: str
    owner: str
    row_estimate: int
    size: str


class EventTriggerOut(BaseModel):
    name: str
    enabled: str
    function_name: str
