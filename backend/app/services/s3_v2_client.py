"""Минимальный S3-клиент: Signature V2, path-style. Без boto3."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import quote

import urllib3


@dataclass
class S3ListedObject:
    object_name: str
    size: int | None
    last_modified: dt.datetime | None


class S3ObjectStream:
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


class S3V2Error(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"S3 operation failed; code: {code}, message: {message}")


def _encode_object_key(key: str) -> str:
    return "/".join(quote(part, safe="") for part in key.split("/"))


def _parse_s3_error(body: bytes) -> tuple[str, str]:
    try:
        root = ET.fromstring(body)
        code = root.findtext("Code") or "Unknown"
        message = root.findtext("Message") or body.decode("utf-8", errors="replace")
        return code, message
    except ET.ParseError:
        return "Unknown", body.decode("utf-8", errors="replace")


def _parse_iso8601(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_http_date() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _encode_query(query: dict[str, str]) -> str:
    pairs = [f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(query.items())]
    return "&".join(pairs)


class S3V2Client:
    """Path-style S3 REST с AWS Signature Version 2."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool):
        self._host = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._scheme = "https" if secure else "http"
        self._http = urllib3.PoolManager(
            cert_reqs="CERT_REQUIRED" if secure else "CERT_NONE",
        )

    def _canonicalized_resource(self, bucket: str, key: str = "", query: dict[str, str] | None = None) -> str:
        resource = f"/{bucket}"
        if key:
            resource += f"/{_encode_object_key(key)}"
        if query:
            resource += "?" + _encode_query(query)
        return resource

    def _authorization(self, method: str, resource: str, date: str, content_md5: str = "", content_type: str = "") -> str:
        string_to_sign = "\n".join([method, content_md5, content_type, date, resource])
        digest = hmac.new(
            self._secret_key.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(digest).decode("ascii")
        return f"AWS {self._access_key}:{signature}"

    def _request(
        self,
        method: str,
        bucket: str,
        key: str = "",
        query: dict[str, str] | None = None,
        body=None,                          # bytes ЛИБО file-like (стриминг без чтения в RAM)
        content_type: str = "",
        content_length: int | None = None,  # обязателен для file-like body
        retries=None,
    ) -> urllib3.HTTPResponse:
        resource = self._canonicalized_resource(bucket, key, query)
        path = resource.split("?", 1)[0]
        query_string = resource.split("?", 1)[1] if "?" in resource else None
        url = f"{self._scheme}://{self._host}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        date = _format_http_date()
        content_md5 = ""
        # MD5 считаем только для bytes-тел. Для file-like (стриминг) не читаем файл
        # в память — Content-MD5 в подписи S3 v2 опционален.
        if isinstance(body, (bytes, bytearray)):
            content_md5 = base64.b64encode(hashlib.md5(body).digest()).decode("ascii")

        headers = {
            "Date": date,
            "Authorization": self._authorization(method, resource, date, content_md5, content_type),
        }
        if content_type:
            headers["Content-Type"] = content_type
        if content_md5:
            headers["Content-MD5"] = content_md5
        if content_length is not None:
            headers["Content-Length"] = str(content_length)

        req_kwargs = {"body": body, "headers": headers, "preload_content": False}
        if retries is not None:
            req_kwargs["retries"] = retries
        response = self._http.request(method, url, **req_kwargs)
        if response.status >= 400:
            data = response.read()
            response.release_conn()
            code, message = _parse_s3_error(data)
            raise S3V2Error(code, message)
        return response

    def probe_bucket(self, bucket: str) -> None:
        response = self._request("HEAD", bucket)
        response.release_conn()

    def fput_object(self, bucket: str, object_name: str, file_path: str) -> None:
        # Потоковая заливка: файл не читается в память (был `body = fh.read()` → OOM
        # на многогигабайтных дампах). urllib3 стримит file-like по Content-Length.
        # retries=False — при переотправке уже вычитанный файл дал бы битую загрузку.
        size = os.path.getsize(file_path)
        with open(file_path, "rb") as fh:
            response = self._request(
                "PUT", bucket, object_name, body=fh,
                content_type="application/octet-stream",
                content_length=size, retries=False,
            )
        response.release_conn()

    def fget_object(self, bucket: str, object_name: str, file_path: str) -> None:
        response = self._request("GET", bucket, object_name)
        try:
            with open(file_path, "wb") as fh:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
        finally:
            response.release_conn()

    def remove_object(self, bucket: str, object_name: str) -> None:
        response = self._request("DELETE", bucket, object_name)
        response.release_conn()

    def get_object(self, bucket: str, object_name: str) -> S3ObjectStream:
        return S3ObjectStream(self._request("GET", bucket, object_name))

    def list_objects(
        self, bucket: str, prefix: str = "", recursive: bool = True
    ) -> Iterator[S3ListedObject]:
        marker = ""
        delimiter = "" if recursive else "/"
        while True:
            query: dict[str, str] = {"max-keys": "1000"}
            if prefix:
                query["prefix"] = prefix
            if delimiter:
                query["delimiter"] = delimiter
            if marker:
                query["marker"] = marker

            response = self._request("GET", bucket, query=query)
            try:
                data = response.read()
            finally:
                response.release_conn()

            root = ET.fromstring(data)
            ns = {"s3": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
            tag = lambda name: f"{{{ns['s3']}}}{name}" if ns else name

            for item in root.findall(f".//{tag('Contents')}"):
                key = item.findtext(tag("Key")) or ""
                size_text = item.findtext(tag("Size"))
                size = int(size_text) if size_text is not None else None
                last_modified = _parse_iso8601(item.findtext(tag("LastModified")))
                if key and (recursive or "/" not in key[len(prefix):].strip("/")):
                    yield S3ListedObject(object_name=key, size=size, last_modified=last_modified)

            is_truncated = (root.findtext(tag("IsTruncated")) or "").lower() == "true"
            if not is_truncated:
                break
            next_marker = root.findtext(tag("NextMarker"))
            if not next_marker:
                contents = root.findall(f".//{tag('Contents')}")
                if not contents:
                    break
                next_marker = contents[-1].findtext(tag("Key")) or ""
            if not next_marker or next_marker == marker:
                break
            marker = next_marker
