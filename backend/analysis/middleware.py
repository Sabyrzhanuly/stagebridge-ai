from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class SimpleCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.headers.get("Origin")
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if origin in settings.CORS_ALLOWED_ORIGINS:
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept-Language"
            response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
        return response
