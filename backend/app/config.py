from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # ── Компоненты внутренней инфраструктуры (сеть compose) ──
    # Хост/порт/пользователь/имя БД фиксированы сетью и меняются редко.
    # При ротации трогаем ТОЛЬКО *_password — единственный источник правды,
    # из него собираются полные URL (см. свойства ниже). Больше не дублируем
    # пароль отдельно в переменной и внутри URL.
    appdb_host: str = "appdb"
    appdb_port: int = 5432
    appdb_user: str = "pgadmin"
    appdb_name: str = "pgadmin"
    appdb_password: str = "pgadmin"

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "pgadmin"
    rabbitmq_password: str = "guest"

    # Явный override полного URL — для внешних/managed-сервисов.
    # Пусто → URL собирается из компонентов выше.
    app_db_url_override: str = Field(default="", validation_alias="APP_DB_URL")
    app_db_url_sync_override: str = Field(default="", validation_alias="APP_DB_URL_SYNC")
    redis_url_override: str = Field(default="", validation_alias="REDIS_URL")
    rabbitmq_url_override: str = Field(default="", validation_alias="RABBITMQ_URL")

    fernet_key: str = "your-fernet-key-here"
    # Отдельный секрет для подписи JWT (НЕ переиспользуем fernet_key).
    # Без значения — fail-fast при первой выдаче/проверке токена.
    jwt_secret: str = ""

    # Разрешённые Origin для CORS (через запятую). При credentials=True
    # wildcard "*" недопустим по спеке — держим явный список.
    cors_origins: str = "http://localhost,http://localhost:5173,http://127.0.0.1:5173"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "pgadmin@example.com"

    allow_registration: bool = False

    # ── ИИ (OpenAI) ──
    # Пусто → ИИ-функции отключены, эндпоинты вернут понятную ошибку.
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    super_admin_username: str = "admin"
    super_admin_email: str = "admin@localhost"
    super_admin_password: str = "admin"

    # ── Полные URL: override или сборка из компонентов ──
    # quote(...) страхует от спецсимволов в пароле (token_urlsafe и так URL-safe).
    @property
    def app_db_url(self) -> str:
        if self.app_db_url_override:
            return self.app_db_url_override
        return (
            f"postgresql+asyncpg://{self.appdb_user}:{quote(self.appdb_password, safe='')}"
            f"@{self.appdb_host}:{self.appdb_port}/{self.appdb_name}"
        )

    @property
    def app_db_url_sync(self) -> str:
        if self.app_db_url_sync_override:
            return self.app_db_url_sync_override
        return (
            f"postgresql://{self.appdb_user}:{quote(self.appdb_password, safe='')}"
            f"@{self.appdb_host}:{self.appdb_port}/{self.appdb_name}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_url_override:
            return self.redis_url_override
        auth = f":{quote(self.redis_password, safe='')}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def rabbitmq_url(self) -> str:
        if self.rabbitmq_url_override:
            return self.rabbitmq_url_override
        return (
            f"amqp://{self.rabbitmq_user}:{quote(self.rabbitmq_password, safe='')}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}//"
        )


settings = Settings()
