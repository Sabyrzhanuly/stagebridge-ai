import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api import ai as ai_api
from app.api.deps import get_auth_context
from app.database import get_db
from app.services import ai_service


@pytest_asyncio.fixture
async def client():
    app = FastAPI()
    app.include_router(ai_api.router, prefix="/api")

    async def override_auth():
        return SimpleNamespace(user=object(), org=None)

    async def override_db():
        yield object()

    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[get_db] = override_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def configured_ai(monkeypatch):
    async def require_key(_db):
        return "test-key", "gpt-5.6"

    monkeypatch.setattr(ai_api, "_require_key", require_key)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "body", "chat_result", "expected_keys"),
    [
        (
            "/api/ai/migration-plan",
            {"diff_summary": "add column", "generated_sql": "ALTER TABLE ..."},
            json.dumps(
                {
                    "overall_risk": "medium",
                    "summary": "Review required",
                    "risks": [],
                    "steps": [],
                    "rollback": [],
                }
            ),
            {"overall_risk", "summary", "risks", "steps", "rollback"},
        ),
        (
            "/api/ai/assistant",
            {"question": "How do I inspect locks?"},
            "Inspect pg_stat_activity and pg_locks.",
            {"answer"},
        ),
        (
            "/api/ai/diagnostics",
            {"payload": "{}"},
            json.dumps(
                {
                    "severity": "ok",
                    "findings": [],
                    "recommendations": [],
                    "quick_wins": [],
                }
            ),
            {"severity", "findings", "recommendations", "quick_wins"},
        ),
        (
            "/api/ai/backup-analysis",
            {"payload": "{}"},
            json.dumps(
                {
                    "risk": "low",
                    "summary": "Backup is recent",
                    "checks": [],
                    "cautions": [],
                }
            ),
            {"risk", "summary", "checks", "cautions"},
        ),
    ],
)
async def test_existing_ai_endpoints_keep_their_contracts(
    client, configured_ai, monkeypatch, path, body, chat_result, expected_keys
):
    async def fake_chat(*_args, **_kwargs):
        return chat_result

    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(path, json={**body, "lang": "en"})

    assert response.status_code == 200
    assert set(response.json()) == expected_keys


@pytest.mark.asyncio
async def test_query_advisor_returns_contract_and_uses_requested_language(
    client, configured_ai, monkeypatch
):
    calls = []

    async def fake_chat(api_key, model, system, user, **kwargs):
        calls.append((api_key, model, system, user, kwargs))
        return json.dumps(
            {
                "severity": "warning",
                "summary": "Sequential scan",
                "problems": ["Missing index"],
                "indexes": ["CREATE INDEX ..."],
                "rewrite": ["Filter earlier"],
                "notes": ["Validate on staging"],
            }
        )

    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(
        "/api/ai/query-advisor",
        json={"payload": '{"query":"select * from orders"}', "lang": "en"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "severity",
        "summary",
        "problems",
        "indexes",
        "rewrite",
        "notes",
    }
    assert calls[0][0:2] == ("test-key", "gpt-5.6")
    assert "in English" in calls[0][2]
    assert calls[0][4]["json_mode"] is True


@pytest.mark.asyncio
async def test_query_advisor_adds_explain_plan_to_ai_context(
    client, configured_ai, monkeypatch
):
    captured_users = []

    async def fake_get_owned_server(server_id, _user, org, _db):
        assert server_id == 7
        assert org is None
        return object()

    async def fake_explain(_server, query, database):
        assert query == "SELECT * FROM orders"
        assert database == "demo_shop"
        return [{"Plan": {"Node Type": "Seq Scan"}}]

    async def fake_chat(_api_key, _model, _system, user, **_kwargs):
        captured_users.append(user)
        return json.dumps(
            {
                "severity": "warning",
                "summary": "Plan grounded",
                "problems": [],
                "indexes": [],
                "rewrite": [],
                "notes": [],
            }
        )

    monkeypatch.setattr(ai_api, "get_owned_server", fake_get_owned_server)
    monkeypatch.setattr(ai_api.query_plan_service, "explain_query", fake_explain)
    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(
        "/api/ai/query-advisor",
        json={
            "payload": json.dumps(
                {
                    "server_id": 7,
                    "database": "demo_shop",
                    "query": "SELECT * FROM orders",
                }
            ),
            "lang": "en",
        },
    )

    assert response.status_code == 200
    assert '"explain_plan"' in captured_users[0]
    assert '"Node Type": "Seq Scan"' in captured_users[0]


@pytest.mark.asyncio
async def test_query_advisor_falls_back_when_explain_fails(
    client, configured_ai, monkeypatch
):
    captured_users = []

    async def fake_get_owned_server(_server_id, _user, _org, _db):
        return object()

    async def failed_explain(_server, _query, _database):
        raise TimeoutError("plan timeout")

    async def fake_chat(_api_key, _model, _system, user, **_kwargs):
        captured_users.append(user)
        return json.dumps(
            {
                "severity": "warning",
                "summary": "Text only",
                "problems": [],
                "indexes": [],
                "rewrite": [],
                "notes": [],
            }
        )

    monkeypatch.setattr(ai_api, "get_owned_server", fake_get_owned_server)
    monkeypatch.setattr(ai_api.query_plan_service, "explain_query", failed_explain)
    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(
        "/api/ai/query-advisor",
        json={
            "payload": json.dumps(
                {"server_id": 7, "database": "demo_shop", "query": "SELECT 1"}
            )
        },
    )

    assert response.status_code == 200
    assert '"explain_plan"' not in captured_users[0]


@pytest.mark.asyncio
async def test_lock_analysis_returns_contract_and_uses_requested_language(
    client, configured_ai, monkeypatch
):
    calls = []

    async def fake_chat(api_key, model, system, user, **kwargs):
        calls.append((api_key, model, system, user, kwargs))
        return json.dumps(
            {
                "severity": "critical",
                "summary": "Ұзақ блоктау тізбегі",
                "blocking_chains": ["PID 10 blocks PID 20"],
                "recommendations": ["Inspect PID 10 transaction"],
                "notes": ["Advisory only"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(
        "/api/ai/lock-analysis",
        json={"payload": '{"locks":[]}', "lang": "kk"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "severity",
        "summary",
        "blocking_chains",
        "recommendations",
        "notes",
    }
    assert calls[0][0:2] == ("test-key", "gpt-5.6")
    assert "қазақ тілінде" in calls[0][2]
    assert calls[0][4]["json_mode"] is True


@pytest.mark.asyncio
async def test_config_advisor_returns_contract_and_uses_requested_language(
    client, configured_ai, monkeypatch
):
    calls = []

    async def fake_chat(api_key, model, system, user, **kwargs):
        calls.append((api_key, model, system, user, kwargs))
        return json.dumps(
            {
                "severity": "warning",
                "summary": "Tune memory settings",
                "findings": ["work_mem is conservative"],
                "recommendations": ["Consider SET work_mem = '16MB' for heavy reporting sessions"],
                "notes": ["Advisory only"],
            }
        )

    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(
        "/api/ai/config-advisor",
        json={"payload": '{"settings":[]}', "lang": "en"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "severity",
        "summary",
        "findings",
        "recommendations",
        "notes",
    }
    assert calls[0][0:2] == ("test-key", "gpt-5.6")
    assert "in English" in calls[0][2]
    assert calls[0][4]["json_mode"] is True


@pytest.mark.asyncio
async def test_schema_review_returns_contract_and_uses_schema_metadata(
    client, configured_ai, monkeypatch
):
    captured_users = []

    async def fake_get_owned_server(server_id, _user, org, _db):
        assert server_id == 7
        assert org is None
        return object()

    async def fake_collect(_server, database):
        assert database == "demo_shop"
        return {
            "database": database,
            "tables": [{"schema_name": "public", "table_name": "orders"}],
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
            "indexes": [],
        }

    async def fake_chat(_api_key, _model, _system, user, **_kwargs):
        captured_users.append(user)
        return json.dumps(
            {
                "severity": "warning",
                "summary": "Schema needs review",
                "issues": ["orders has no primary key in snapshot"],
                "recommendations": ["Consider ALTER TABLE orders ADD PRIMARY KEY (...)"],
                "notes": ["Advisory only"],
            }
        )

    monkeypatch.setattr(ai_api, "get_owned_server", fake_get_owned_server)
    monkeypatch.setattr(ai_api.schema_review_service, "collect_schema_metadata", fake_collect)
    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    response = await client.post(
        "/api/ai/schema-review",
        json={"server_id": 7, "database": "demo_shop", "lang": "en"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "severity",
        "summary",
        "issues",
        "recommendations",
        "notes",
    }
    assert '"database": "demo_shop"' in captured_users[0]
    assert '"table_name": "orders"' in captured_users[0]


@pytest.mark.asyncio
async def test_schema_review_tenant_authorizes_database_access(monkeypatch):
    calls = []
    auth = SimpleNamespace(user=object(), org=SimpleNamespace(organization_id=42))

    async def require_key(_db):
        return "test-key", "gpt-5.6"

    async def fake_get_owned_server(server_id, user, org, db):
        calls.append(("server", server_id, user, org, db))
        return object()

    async def fake_ensure_database_access(org, server_id, database, db):
        calls.append(("database", org, server_id, database, db))

    async def fake_collect(_server, database):
        calls.append(("collect", database))
        return {"database": database, "tables": []}

    async def fake_schema_review(_api_key, _model, payload, lang):
        calls.append(("ai", payload, lang))
        return {
            "severity": "ok",
            "summary": "ok",
            "issues": [],
            "recommendations": [],
            "notes": [],
        }

    monkeypatch.setattr(ai_api, "_require_key", require_key)
    monkeypatch.setattr(ai_api, "get_owned_server", fake_get_owned_server)
    monkeypatch.setattr(ai_api, "ensure_database_access", fake_ensure_database_access)
    monkeypatch.setattr(ai_api.schema_review_service, "collect_schema_metadata", fake_collect)
    monkeypatch.setattr(ai_api.ai_service, "schema_review", fake_schema_review)

    response = await ai_api.ai_schema_review(
        ai_api.SchemaReviewIn(server_id=7, database="demo_shop", lang="kk"),
        db=object(),
        auth=auth,
    )

    assert response["severity"] == "ok"
    assert calls[0][0] == "server"
    assert calls[1] == ("database", auth.org, 7, "demo_shop", calls[0][4])
    assert calls[2] == ("collect", "demo_shop")
    assert calls[3][2] == "kk"


@pytest.mark.asyncio
async def test_nl_to_sql_rejects_non_select_without_execution(client, configured_ai, monkeypatch):
    async def fake_get_owned_server(server_id, _user, org, _db):
        assert server_id == 7
        assert org is None
        return object()

    async def fake_collect(_server, database):
        assert database == "demo_shop"
        return {"database": database, "tables": [{"table_name": "orders"}]}

    async def fake_nl_to_sql(_api_key, _model, question, schema_context, lang):
        assert question == "delete old orders"
        assert schema_context["database"] == "demo_shop"
        assert lang == "en"
        return {
            "sql": "DELETE FROM orders WHERE created_at < now() - interval '1 year'",
            "explanation": "This is not read-only.",
            "notes": ["Rejected by policy"],
        }

    async def forbidden_runner(*_args, **_kwargs):
        raise AssertionError("unsafe SQL must not be executed")

    monkeypatch.setattr(ai_api, "get_owned_server", fake_get_owned_server)
    monkeypatch.setattr(ai_api.schema_review_service, "collect_schema_metadata", fake_collect)
    monkeypatch.setattr(ai_api.ai_service, "nl_to_sql", fake_nl_to_sql)
    monkeypatch.setattr(ai_api.query_plan_service, "run_readonly_select", forbidden_runner)

    response = await client.post(
        "/api/ai/nl-to-sql",
        json={
            "server_id": 7,
            "database": "demo_shop",
            "question": "delete old orders",
            "lang": "en",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "sql": "DELETE FROM orders WHERE created_at < now() - interval '1 year'",
        "explanation": "This is not read-only.",
        "notes": ["Rejected by policy"],
        "executed": False,
        "reason": "not a safe read-only SELECT",
    }


@pytest.mark.asyncio
async def test_nl_to_sql_executes_valid_select_through_safe_runner(client, configured_ai, monkeypatch):
    async def fake_get_owned_server(server_id, _user, org, _db):
        assert server_id == 7
        assert org is None
        return SimpleNamespace(name="demo")

    async def fake_collect(_server, database):
        return {"database": database, "tables": [{"table_name": "orders"}]}

    async def fake_nl_to_sql(_api_key, _model, question, _schema_context, lang):
        assert question == "show latest orders"
        assert lang == "kk"
        return {
            "sql": "SELECT id, total FROM orders ORDER BY id DESC LIMIT 20",
            "explanation": "Latest orders by id.",
            "notes": [],
        }

    async def fake_runner(server, sql, database):
        assert server.name == "demo"
        assert sql == "SELECT id, total FROM orders ORDER BY id DESC LIMIT 20"
        assert database == "demo_shop"
        return {
            "columns": ["id", "total"],
            "rows": [{"id": 2, "total": 120}],
            "row_count": 1,
        }

    monkeypatch.setattr(ai_api, "get_owned_server", fake_get_owned_server)
    monkeypatch.setattr(ai_api.schema_review_service, "collect_schema_metadata", fake_collect)
    monkeypatch.setattr(ai_api.ai_service, "nl_to_sql", fake_nl_to_sql)
    monkeypatch.setattr(ai_api.query_plan_service, "run_readonly_select", fake_runner)

    response = await client.post(
        "/api/ai/nl-to-sql",
        json={
            "server_id": 7,
            "database": "demo_shop",
            "question": "show latest orders",
            "lang": "kk",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "sql": "SELECT id, total FROM orders ORDER BY id DESC LIMIT 20",
        "explanation": "Latest orders by id.",
        "notes": [],
        "executed": True,
        "columns": ["id", "total"],
        "rows": [{"id": 2, "total": 120}],
        "row_count": 1,
    }


@pytest.mark.asyncio
async def test_status_reports_unavailable_without_configured_key(client, monkeypatch):
    async def no_db_setting(_db, _key):
        return None

    monkeypatch.setattr(ai_api.app_settings_service, "get_setting", no_db_setting)
    monkeypatch.setattr(ai_api.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_api.settings, "openai_model", "gpt-5.6")

    response = await client.get("/api/ai/status")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "model": None,
        "source": "none",
    }
