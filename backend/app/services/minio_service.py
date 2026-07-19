import time
import threading
from dataclasses import dataclass
from typing import Any, Union

from minio import Minio
from minio.error import S3Error
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.services.s3_v2_client import S3V2Client, S3V2Error
from app.services.swift_client import (
    SwiftClient,
    SwiftError,
    normalize_swift_auth_url,
    parse_swift_identity,
)

StorageClient = Union[Minio, S3V2Client, SwiftClient]


class MinioNotConfiguredError(Exception):
    """S3/Swift хранилище не настроено для сервера."""

    def __init__(self, server_id: int, message: str | None = None):
        self.server_id = server_id
        super().__init__(
            message
            or f"Для сервера #{server_id} не выбрано хранилище. "
            "Добавьте хранилище в «Настройки → Хранилище» и привяжите к серверу."
        )


@dataclass
class _StorageParams:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool
    region: str | None = None
    sign_version: str = "v4"
    api_type: str = "s3"
    swift_project: str | None = None
    swift_domain: str | None = None


_lock = threading.Lock()
_clients: dict[int, StorageClient] = {}
_params: dict[int, _StorageParams | None] = {}
_loaded_at: dict[int, float] = {}
_CACHE_TTL = 60.0


def normalize_s3_endpoint(endpoint: str, secure: bool | None = None) -> tuple[str, bool]:
    """host:port без схемы; https:// в endpoint включает TLS."""
    raw = endpoint.strip()
    if not raw:
        return raw, secure if secure is not None else False

    detected_secure = secure if secure is not None else False
    if raw.startswith("https://"):
        raw = raw[8:]
        detected_secure = True
    elif raw.startswith("http://"):
        raw = raw[7:]
        detected_secure = False

    raw = raw.split("/", 1)[0].rstrip("/")
    if ":" in raw:
        host, port = raw.rsplit(":", 1)
        if detected_secure and port == "443":
            raw = host
        elif not detected_secure and port == "80":
            raw = host
    return raw, detected_secure


def _normalize_sign_version(value: str | None) -> str:
    if value and value.strip().lower() in ("v2", "2"):
        return "v2"
    return "v4"


def _normalize_api_type(value: str | None) -> str:
    if value and value.strip().lower() == "swift":
        return "swift"
    return "s3"


def _normalize_endpoint(api_type: str, endpoint: str, secure: bool) -> tuple[str, bool]:
    if api_type == "swift":
        return normalize_swift_auth_url(endpoint, secure)
    return normalize_s3_endpoint(endpoint, secure)


def normalize_api_type(value: str | None) -> str:
    return _normalize_api_type(value)


def normalize_storage_endpoint(api_type: str, endpoint: str, secure: bool) -> tuple[str, bool]:
    return _normalize_endpoint(api_type, endpoint, secure)


def _make_client(params: _StorageParams) -> StorageClient:
    if params.api_type == "swift":
        project, domain, username = parse_swift_identity(
            params.access_key,
            params.swift_project,
            params.swift_domain,
        )
        return SwiftClient(
            auth_url=params.endpoint,
            username=username,
            password=params.secret_key,
            project=project,
            domain=domain,
            secure=params.secure,
        )
    if params.sign_version == "v2":
        return S3V2Client(
            endpoint=params.endpoint,
            access_key=params.access_key,
            secret_key=params.secret_key,
            secure=params.secure,
        )
    kwargs: dict = {
        "access_key": params.access_key,
        "secret_key": params.secret_key,
        "secure": params.secure,
    }
    if params.region:
        kwargs["region"] = params.region
    return Minio(params.endpoint, **kwargs)


def _load_params_from_db(storage_id: int) -> _StorageParams | None:
    try:
        from app.models.minio_config import MinioConfig
        engine = create_engine(settings.app_db_url_sync)
        with Session(engine) as session:
            row = session.get(MinioConfig, storage_id)
        engine.dispose()
        if row:
            api_type = _normalize_api_type(row.api_type)
            endpoint, secure = _normalize_endpoint(api_type, row.endpoint, row.secure)
            region = (row.region or "").strip() or None
            return _StorageParams(
                endpoint=endpoint,
                access_key=row.access_key,
                secret_key=row.secret_key,
                bucket=row.bucket,
                secure=secure,
                region=region,
                sign_version=_normalize_sign_version(row.sign_version),
                api_type=api_type,
                swift_project=(row.swift_project or "").strip() or None,
                swift_domain=(row.swift_domain or "").strip() or None,
            )
    except Exception:
        pass
    return None


def _load_storage_id_for_server(server_id: int) -> int | None:
    try:
        from app.models.server import Server
        engine = create_engine(settings.app_db_url_sync)
        with Session(engine) as session:
            server = session.get(Server, server_id)
            storage_id = server.storage_id if server else None
        engine.dispose()
        return storage_id
    except Exception:
        return None


def _refresh_params_cache(storage_id: int) -> _StorageParams | None:
    params = _load_params_from_db(storage_id)
    _params[storage_id] = params
    _loaded_at[storage_id] = time.monotonic()
    return params


def _require_params(storage_id: int) -> _StorageParams:
    now = time.monotonic()
    cached_at = _loaded_at.get(storage_id, 0.0)
    if storage_id not in _params or (now - cached_at) > _CACHE_TTL:
        _refresh_params_cache(storage_id)
    params = _params.get(storage_id)
    if not params:
        raise MinioNotConfiguredError(0, f"Хранилище #{storage_id} не найдено")
    return params


def _resolve_storage_id(server_id: int, storage_id: int | None = None) -> int:
    if storage_id is not None:
        return storage_id
    resolved = _load_storage_id_for_server(server_id)
    if not resolved:
        raise MinioNotConfiguredError(server_id)
    return resolved


def is_configured(server_id: int) -> bool:
    try:
        _resolve_storage_id(server_id)
        return True
    except MinioNotConfiguredError:
        return False


def is_storage_configured(storage_id: int) -> bool:
    try:
        _require_params(storage_id)
        return True
    except MinioNotConfiguredError:
        return False


def invalidate_cache(storage_id: int | None = None) -> None:
    with _lock:
        if storage_id is None:
            _clients.clear()
            _params.clear()
            _loaded_at.clear()
        else:
            _clients.pop(storage_id, None)
            _params.pop(storage_id, None)
            _loaded_at.pop(storage_id, None)


def get_minio_client(storage_id: int) -> StorageClient:
    with _lock:
        if storage_id not in _clients:
            params = _require_params(storage_id)
            _clients[storage_id] = _make_client(params)
        return _clients[storage_id]


def _bucket(storage_id: int) -> str:
    return _require_params(storage_id).bucket


def _probe_bucket(client: StorageClient, bucket: str) -> None:
    if isinstance(client, SwiftClient):
        client.probe_container(bucket)
        return
    if isinstance(client, S3V2Client):
        client.probe_bucket(bucket)
        return
    next(client.list_objects(bucket, recursive=False), None)


def upload_file(
    server_id: int,
    file_path: str,
    object_name: str,
    *,
    storage_id: int | None = None,
) -> str:
    sid = _resolve_storage_id(server_id, storage_id)
    client = get_minio_client(sid)
    bucket = _bucket(sid)
    client.fput_object(bucket, object_name, file_path)
    return f"{bucket}/{object_name}"


def download_file(
    server_id: int,
    object_name: str,
    file_path: str,
    *,
    storage_id: int | None = None,
) -> None:
    sid = _resolve_storage_id(server_id, storage_id)
    client = get_minio_client(sid)
    client.fget_object(_bucket(sid), object_name, file_path)


def delete_file(
    server_id: int,
    object_name: str,
    *,
    storage_id: int | None = None,
) -> None:
    try:
        sid = _resolve_storage_id(server_id, storage_id)
        client = get_minio_client(sid)
        client.remove_object(_bucket(sid), object_name)
    except MinioNotConfiguredError:
        return
    except Exception as e:  # noqa: BLE001 — не молчим: осиротевший объект в S3 виден в логе
        print(f"[storage] удаление объекта {object_name} не удалось "
              f"(файл мог остаться в хранилище): {type(e).__name__}: {e}", flush=True)


def list_backups(server_id: int, prefix: str = "", *, storage_id: int | None = None) -> list[dict]:
    sid = _resolve_storage_id(server_id, storage_id)
    client = get_minio_client(sid)
    objects = client.list_objects(_bucket(sid), prefix=prefix, recursive=True)
    return [
        {"name": obj.object_name, "size": obj.size, "last_modified": obj.last_modified}
        for obj in objects
    ]


def get_object_stream(server_id: int, object_name: str, *, storage_id: int | None = None) -> Any:
    try:
        sid = _resolve_storage_id(server_id, storage_id)
        client = get_minio_client(sid)
        return client.get_object(_bucket(sid), object_name)
    except Exception as e:  # noqa: BLE001 — причина (доступ/сеть) в лог, наружу None → 404
        print(f"[storage] чтение объекта {object_name} не удалось: {type(e).__name__}: {e}", flush=True)
        return None


def test_connection(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    secure: bool,
    region: str | None = None,
    sign_version: str = "v4",
    api_type: str = "s3",
    swift_project: str | None = None,
    swift_domain: str | None = None,
) -> dict:
    try:
        api = _normalize_api_type(api_type)
        endpoint_norm, secure_norm = _normalize_endpoint(api, endpoint, secure)
        bucket_name = bucket.strip()
        params = _StorageParams(
            endpoint=endpoint_norm,
            access_key=access_key.strip(),
            secret_key=secret_key.strip(),
            bucket=bucket_name,
            secure=secure_norm,
            region=(region or "").strip() or None,
            sign_version=_normalize_sign_version(sign_version),
            api_type=api,
            swift_project=(swift_project or "").strip() or None,
            swift_domain=(swift_domain or "").strip() or None,
        )
        client = _make_client(params)
        _probe_bucket(client, bucket_name)
        label = "контейнер" if api == "swift" else "bucket"
        return {
            "ok": True,
            "message": f"Подключено. Доступ к {label} '{bucket_name}' подтверждён.",
        }
    except Exception as e:
        msg = str(e)
        if "AccessDenied" in msg or "Access Denied" in msg or "403" in msg:
            msg += ". Проверьте учётные данные и права на чтение/запись."
        return {"ok": False, "message": msg}
