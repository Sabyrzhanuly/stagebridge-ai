from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler as drf_exception_handler

from .services.localization import request_locale, translate


def localized_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    locale = request_locale(context["request"])
    if response.status_code == 404:
        response.data = {"error": translate("errors.not_found", locale), "code": "not_found"}
    elif isinstance(exc, ValidationError):
        response.data = {
            "error": translate("errors.bad_request", locale),
            "code": "validation_error",
            "field_errors": _localize_validation(response.data, exc.get_codes(), locale),
        }
    return response


def _localize_validation(data, codes, locale):
    if isinstance(data, dict):
        return {key: _localize_validation(value, codes.get(key, "invalid") if isinstance(codes, dict) else codes, locale) for key, value in data.items()}
    if isinstance(data, list):
        code_list = codes if isinstance(codes, list) else [codes] * len(data)
        return [_localize_validation(value, code_list[index] if index < len(code_list) else "invalid", locale) for index, value in enumerate(data)]
    code = str(codes or "invalid")
    key = {
        "required": "validation.required", "blank": "validation.blank", "unique": "validation.unique",
        "select_schema": "validation.select_schema", "timeout": "validation.timeout", "password": "validation.password",
    }.get(code, "validation.invalid")
    return translate(key, locale)
