from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "stagebridge-dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "analysis",
]

MIDDLEWARE = [
    "analysis.middleware.SimpleCorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "stagebridge.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
WSGI_APPLICATION = "stagebridge.wsgi.application"


def database_settings() -> dict[str, object]:
    if os.getenv("BACKEND_DB_ENGINE", "sqlite") == "postgres":
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("BACKEND_DB_NAME", "stagebridge_backend"),
            "USER": os.getenv("BACKEND_DB_USER", "stagebridge"),
            "PASSWORD": os.getenv("BACKEND_DB_PASSWORD", "stagebridge"),
            "HOST": os.getenv("BACKEND_DB_HOST", "localhost"),
            "PORT": os.getenv("BACKEND_DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"options": "-c statement_timeout=10000"},
        }
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }


DATABASES = {"default": database_settings()}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "URL_FORMAT_OVERRIDE": None,
    "EXCEPTION_HANDLER": "analysis.exceptions.localized_exception_handler",
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
