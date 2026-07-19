from pydantic import BaseModel


class ConnectionStats(BaseModel):
    total: int
    active: int
    idle: int
    waiting: int
    max_connections: int = 0


class DatabaseSize(BaseModel):
    datname: str
    size: str
    size_bytes: int


class SlowQuery(BaseModel):
    query: str
    calls: int
    mean_time_ms: float
    total_time_ms: float


class SlowQueriesMeta(BaseModel):
    available: bool
    error: str | None = None
    hint: str | None = None


class LockInfo(BaseModel):
    pid: int
    relation: str | None
    mode: str
    granted: bool
    query: str | None
    wait_duration: str | None


class TablespaceSize(BaseModel):
    name: str
    size_bytes: int


class StorageStats(BaseModel):
    total_db_bytes: int
    tablespaces: list[TablespaceSize] = []


class MonitoringSnapshot(BaseModel):
    connections: ConnectionStats
    cache_hit_ratio: float | None = None
    database_sizes: list[DatabaseSize]
    storage: StorageStats | None = None
    slow_queries: list[SlowQuery]
    slow_queries_meta: SlowQueriesMeta
    locks: list[LockInfo]
    collected_at: str | None = None
    source: str | None = None
