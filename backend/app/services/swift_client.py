"""OpenStack Swift (Keystone v3) — urllib3, без boto3 и python-swiftclient."""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import quote

import urllib3

from app.services.s3_v2_client import S3ListedObject


class SwiftError(Exception):
    def __init__(self, message: str, status: int | None = None):
        self.status = status
        super().__init__(message)


class SwiftObjectStream:
    def __init__(self, response: urllib3.HTTPResponse):
        self._response = response

    def stream(self, chunk_size: int = 32 * 1024):
        while True:
            chunk = self._response.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def close(self):
        self._response.release_conn()

    def release_conn(self):
        self.close()


@dataclass
class _SwiftSession:
    token: str
    storage_url: str
    expires_at: float


def normalize_swift_auth_url(endpoint: str, secure: bool | None = None) -> tuple[str, bool]:
    raw = endpoint.strip()
    if not raw:
        return raw, secure if secure is not None else True

    detected_secure = secure if secure is not None else True
    if raw.startswith("https://"):
        raw = raw[8:]
        detected_secure = True
    elif raw.startswith("http://"):
        raw = raw[7:]
        detected_secure = False

    raw = raw.rstrip("/")
    if not raw.endswith("/v3"):
        raw = f"{raw}/v3"

    scheme = "https" if detected_secure else "http"
    return f"{scheme}://{raw}", detected_secure


def parse_swift_identity(
    access_key: str,
    swift_project: str | None,
    swift_domain: str | None,
) -> tuple[str, str, str]:
    identity = access_key.strip()
    domain = (swift_domain or "default").strip() or "default"
    if identity.count(":") >= 2:
        project, domain_part, username = identity.split(":", 2)
        return project.strip(), domain_part.strip() or domain, username.strip()
    project = (swift_project or "").strip()
    if not project:
        raise SwiftError("Укажите project или username в формате project:domain:username")
    return project, domain, identity


def _encode_object_name(name: str) -> str:
    return "/".join(quote(part, safe="") for part in name.split("/"))


class SwiftClient:
    def __init__(
        self,
        auth_url: str,
        username: str,
        password: str,
        project: str,
        domain: str,
        secure: bool = True,
    ):
        self._auth_url = auth_url.rstrip("/")
        self._username = username
        self._password = password
        self._project = project
        self._domain = domain
        self._http = urllib3.PoolManager(
            cert_reqs="CERT_REQUIRED" if secure else "CERT_NONE",
        )
        self._session: _SwiftSession | None = None
        self._lock = threading.Lock()

    def _authenticate(self) -> _SwiftSession:
        url = f"{self._auth_url}/auth/tokens"
        body = json.dumps({
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": self._username,
                            "domain": {"name": self._domain},
                            "password": self._password,
                        }
                    },
                },
                "scope": {
                    "project": {
                        "name": self._project,
                        "domain": {"name": self._domain},
                    }
                },
            }
        }).encode("utf-8")
        response = self._http.request(
            "POST",
            url,
            body=body,
            headers={"Content-Type": "application/json"},
        )
        if response.status >= 400:
            detail = response.data.decode("utf-8", errors="replace")
            raise SwiftError(f"Swift auth failed ({response.status}): {detail}", response.status)

        token = response.headers.get("X-Subject-Token")
        if not token:
            raise SwiftError("Swift auth: нет X-Subject-Token в ответе")

        payload = json.loads(response.data.decode("utf-8"))
        storage_url = _extract_object_store_url(payload)
        expires = payload.get("token", {}).get("expires_at")
        expires_at = _parse_expires(expires)
        return _SwiftSession(token=token, storage_url=storage_url, expires_at=expires_at)

    def _get_session(self) -> _SwiftSession:
        with self._lock:
            now = time.time()
            if self._session is None or now >= self._session.expires_at - 60:
                self._session = self._authenticate()
            return self._session

    def invalidate_session(self) -> None:
        with self._lock:
            self._session = None

    def _object_url(self, container: str, object_name: str = "") -> str:
        session = self._get_session()
        base = session.storage_url.rstrip("/")
        url = f"{base}/{quote(container, safe='')}"
        if object_name:
            url = f"{url}/{_encode_object_name(object_name)}"
        return url

    def _request(
        self,
        method: str,
        container: str,
        object_name: str = "",
        *,
        query: str = "",
        body=None,                          # bytes ЛИБО file-like (стриминг)
        headers: dict[str, str] | None = None,
        preload_content: bool = True,
        retries=None,
    ) -> urllib3.HTTPResponse:
        session = self._get_session()
        url = self._object_url(container, object_name)
        if query:
            url = f"{url}?{query}"
        req_headers = {"X-Auth-Token": session.token}
        if headers:
            req_headers.update(headers)
        req_kwargs = {"body": body, "headers": req_headers, "preload_content": preload_content}
        if retries is not None:
            req_kwargs["retries"] = retries
        response = self._http.request(method, url, **req_kwargs)
        if response.status == 401:
            self.invalidate_session()
            session = self._get_session()
            req_headers["X-Auth-Token"] = session.token
            url = self._object_url(container, object_name)
            if query:
                url = f"{url}?{query}"
            response = self._http.request(
                method,
                url,
                body=body,
                headers=req_headers,
                preload_content=preload_content,
            )
        if response.status >= 400:
            data = b""
            if preload_content:
                data = response.data
            else:
                data = response.read()
                response.release_conn()
            detail = data.decode("utf-8", errors="replace")
            raise SwiftError(f"Swift {method} failed ({response.status}): {detail}", response.status)
        return response

    def probe_container(self, container: str) -> None:
        response = self._request("HEAD", container)
        response.release_conn()

    def fput_object(self, container: str, object_name: str, file_path: str) -> None:
        # Потоковая заливка: файл не читается в память (был `body = fh.read()` → OOM).
        size = os.path.getsize(file_path)
        with open(file_path, "rb") as fh:
            response = self._request(
                "PUT",
                container,
                object_name,
                body=fh,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(size),
                },
                retries=False,
            )
        response.release_conn()

    def fget_object(self, container: str, object_name: str, file_path: str) -> None:
        response = self._request("GET", container, object_name, preload_content=False)
        try:
            with open(file_path, "wb") as fh:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
        finally:
            response.release_conn()

    def remove_object(self, container: str, object_name: str) -> None:
        response = self._request("DELETE", container, object_name)
        response.release_conn()

    def get_object(self, container: str, object_name: str) -> SwiftObjectStream:
        return SwiftObjectStream(
            self._request("GET", container, object_name, preload_content=False)
        )

    def list_objects(
        self, container: str, prefix: str = "", recursive: bool = True
    ) -> Iterator[S3ListedObject]:
        query_parts = ["format=json"]
        if prefix:
            query_parts.append(f"prefix={quote(prefix, safe='')}")
        if not recursive:
            query_parts.append("delimiter=/")
        marker = ""
        while True:
            parts = list(query_parts)
            if marker:
                parts.append(f"marker={quote(marker, safe='')}")
            response = self._request("GET", container, query="&".join(parts))
            try:
                items = json.loads(response.data.decode("utf-8"))
            finally:
                response.release_conn()
            if not items:
                break
            for item in items:
                name = item.get("name") or item.get("subdir") or ""
                if not name or name.endswith("/"):
                    continue
                if not recursive and "/" in name[len(prefix):].lstrip("/"):
                    continue
                size = item.get("bytes")
                last_modified = _parse_iso8601(item.get("last_modified"))
                yield S3ListedObject(
                    object_name=name,
                    size=int(size) if size is not None else None,
                    last_modified=last_modified,
                )
                marker = name
            if len(items) < 10000:
                break


def _extract_object_store_url(payload: dict) -> str:
    catalog = payload.get("token", {}).get("catalog") or []
    for service in catalog:
        if service.get("type") != "object-store":
            continue
        endpoints = service.get("endpoints") or []
        for iface in ("public", "internal", "admin"):
            for ep in endpoints:
                if ep.get("interface") == iface and ep.get("url"):
                    return ep["url"].rstrip("/")
    raise SwiftError("Swift auth: object-store endpoint не найден в catalog")


def _parse_expires(value: str | None) -> float:
    if not value:
        return time.time() + 3600
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        expires = dt.datetime.fromisoformat(value)
        return expires.timestamp()
    except ValueError:
        return time.time() + 3600


def _parse_iso8601(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None
