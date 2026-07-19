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
