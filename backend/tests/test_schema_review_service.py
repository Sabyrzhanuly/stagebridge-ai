import pytest

from app.services import schema_review_service


class FakeTransaction:
    def __init__(self, connection, readonly):
        self.connection = connection
        self.connection.readonly = readonly

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class FakeConnection:
    readonly = None

    def __init__(self):
        self.execute_calls = []
        self.fetch_calls = []

    def transaction(self, *, readonly):
        return FakeTransaction(self, readonly)

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        if "pg_catalog.pg_class" in sql:
            return [
                {
                    "schema_name": "public",
                    "table_name": "orders",
                    "table_kind": "table",
                    "row_estimate": 1200,
                    "total_bytes": 65536,
                }
            ]
        if "information_schema.columns" in sql:
            return [
                {
                    "schema_name": "public",
                    "table_name": "orders",
                    "column_name": "id",
                    "ordinal_position": 1,
                    "data_type": "bigint",
                    "udt_name": "int8",
                    "nullable": False,
                    "column_default": None,
                    "character_maximum_length": None,
                    "numeric_precision": 64,
                    "numeric_scale": 0,
                }
            ]
        if "PRIMARY KEY" in sql:
            return [
                {
                    "schema_name": "public",
                    "table_name": "orders",
                    "constraint_name": "orders_pkey",
                    "columns": ["id"],
                }
            ]
        if "FOREIGN KEY" in sql:
            return []
        if "pg_catalog.pg_indexes" in sql:
            return [
                {
                    "schema_name": "public",
                    "table_name": "orders",
                    "index_name": "orders_pkey",
                    "index_def": "CREATE UNIQUE INDEX orders_pkey ON public.orders USING btree (id)",
                }
            ]
        return []


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return False


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()
        self.closed = False

    def acquire(self):
        return FakeAcquire(self.connection)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_collect_schema_metadata_is_read_only_bounded_and_closes_pool(monkeypatch):
    pool = FakePool()

    async def fake_pool(_server, database):
        assert database == "demo_shop"
        return pool

    monkeypatch.setattr(schema_review_service, "get_target_pool", fake_pool)

    metadata = await schema_review_service.collect_schema_metadata(
        object(), "demo_shop", max_tables=999, timeout_ms=1_500
    )

    assert metadata["database"] == "demo_shop"
    assert metadata["limits"]["max_tables"] == schema_review_service.MAX_TABLES
    assert metadata["tables"][0]["table_name"] == "orders"
    assert metadata["columns"][0]["column_name"] == "id"
    assert metadata["primary_keys"][0]["columns"] == ["id"]
    assert metadata["indexes"][0]["table"] == "public.orders"
    assert pool.connection.readonly is True
    assert pool.connection.execute_calls == [
        ("select set_config('statement_timeout', $1, true)", ("1500ms",))
    ]
    assert len(pool.connection.fetch_calls) == 5
    assert all(
        call[0].strip().lower().startswith(("select", "with"))
        for call in pool.connection.fetch_calls
    )
    assert pool.closed is True
