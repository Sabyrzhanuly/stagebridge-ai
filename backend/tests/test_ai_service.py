import json

import pytest

from app.services import ai_service


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("ru", "русском языке"),
        ("ru-RU", "русском языке"),
        ("kk", "казахском языке (қазақ тілінде)"),
        ("en-US", "английском языке (in English)"),
        ("de", "русском языке"),
        ("", "русском языке"),
    ],
)
def test_lang_maps_supported_locales_and_falls_back_to_russian(lang, expected):
    assert ai_service._lang(lang) == expected


def test_safe_json_parses_valid_object():
    payload = '{"severity":"warning","summary":"Нужна проверка"}'

    assert ai_service._safe_json(payload) == {
        "severity": "warning",
        "summary": "Нужна проверка",
    }


def test_safe_json_wraps_invalid_text():
    assert ai_service._safe_json("не JSON") == {
        "summary": "не JSON",
        "raw": True,
    }


@pytest.mark.asyncio
async def test_audit_summary_returns_expected_shape_and_json_mode(monkeypatch):
    calls = []

    async def fake_chat(api_key, model, system, user, **kwargs):
        calls.append((api_key, model, system, user, kwargs))
        return json.dumps(
            {
                "summary": "Audit is quiet",
                "highlights": ["one login"],
                "anomalies": [],
                "notes": ["limited sample"],
            }
        )

    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    result = await ai_service.audit_summary(
        "test-key",
        "gpt-5.6",
        '{"records":[{"action":"login"}]}',
        lang="en",
    )

    assert set(result) == {"summary", "highlights", "anomalies", "notes"}
    assert calls[0][0:2] == ("test-key", "gpt-5.6")
    assert "in English" in calls[0][2]
    assert calls[0][4]["json_mode"] is True


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def test_retry_chat_kwargs_swaps_max_tokens_to_completion_tokens():
    kwargs = {"max_tokens": 500, "temperature": 0.2}
    error = ApiError("Unsupported parameter: max_tokens. Use max_completion_tokens instead.")

    assert ai_service._retry_chat_kwargs(kwargs, error) == {
        "max_completion_tokens": 500,
        "temperature": 0.2,
    }
    assert kwargs == {"max_tokens": 500, "temperature": 0.2}


def test_retry_chat_kwargs_swaps_completion_tokens_to_max_tokens():
    kwargs = {"max_completion_tokens": 500}
    error = ApiError("max_completion_tokens is not supported; use max_tokens")

    assert ai_service._retry_chat_kwargs(kwargs, error) == {"max_tokens": 500}


def test_retry_chat_kwargs_strips_unsupported_optional_parameters():
    kwargs = {
        "model": "gpt-5.6",
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    error = ApiError("Unsupported parameters: temperature and response_format")

    assert ai_service._retry_chat_kwargs(kwargs, error) == {"model": "gpt-5.6"}


@pytest.mark.parametrize(
    "error",
    [
        ApiError("Unsupported parameter", status_code=500),
        ApiError("Bad request without a relevant parameter"),
        RuntimeError("network unavailable"),
    ],
)
def test_retry_chat_kwargs_ignores_unrelated_errors(error):
    assert ai_service._retry_chat_kwargs({"model": "gpt-5.6"}, error) is None
