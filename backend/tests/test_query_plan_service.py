import pytest

from app.services import query_plan_service


@pytest.mark.parametrize(
    "query",
    [
        "select * from orders",
        "-- dashboard\nWITH recent AS (SELECT * FROM orders) SELECT * FROM recent",
        "SELECT '; update users' AS harmless_text;",
    ],
)
def test_is_explainable_query_accepts_single_select(query):
    assert query_plan_service.is_explainable_query(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE orders SET status = 'done'",
        "WITH removed AS (DELETE FROM orders RETURNING *) SELECT * FROM removed",
        "SELECT 1; DELETE FROM orders",
        "EXPLAIN SELECT * FROM orders",
        "",
    ],
)
def test_is_explainable_query_rejects_non_select_or_multiple_statements(query):
    assert query_plan_service.is_explainable_query(query) is False


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

    async def fetch(self, sql):
        self.fetch_calls.append(sql)
        return [('[{"Plan":{"Node Type":"Seq Scan"}}]',)]


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
async def test_explain_query_is_read_only_timeout_bounded_and_plan_only(monkeypatch):
    pool = FakePool()

    async def fake_pool(_server, database):
        assert database == "demo_shop"
        return pool

    monkeypatch.setattr(query_plan_service, "get_target_pool", fake_pool)

    plan = await query_plan_service.explain_query(
        object(), "SELECT * FROM demo_orders", "demo_shop", timeout_ms=1_500
    )

    assert plan == [{"Plan": {"Node Type": "Seq Scan"}}]
    assert pool.connection.readonly is True
    assert pool.connection.execute_calls == [
        ("select set_config('statement_timeout', $1, true)", ("1500ms",))
    ]
    assert pool.connection.fetch_calls == [
        "EXPLAIN (FORMAT JSON) SELECT * FROM demo_orders"
    ]
    assert pool.closed is True
