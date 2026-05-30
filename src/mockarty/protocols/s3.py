# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Minimal S3 test client — mirrors ``sdk/go-sdk/protocols/s3``.

Speaks path-style S3 over plain HTTP (``<endpoint>/<bucket>/<key>``) so
CI/CD test scripts can exercise an S3-compatible endpoint — a Mockarty
S3 mock, MinIO, or AWS itself — and assert on PutObject / GetObject /
ListObjects / DeleteObject results.

Why a minimal client: the full AWS SDK (boto3) is a heavy dependency to
pull into every test binary. The operations a test author needs map onto
plain HTTP verbs against a path-style URL, which ride on the core
``httpx`` dependency. For SigV4-signed buckets pass a ``signer`` callable
that mutates the outbound request; against unsigned Mockarty mocks no
signer is needed.

Out of scope: bucket admin (ACL/versioning/lifecycle/multipart),
presigned URLs, and the SigV4 algorithm itself — the owner-rule for the
SDK is "expose only the surface useful from CI/CD scripts and tests".
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import httpx

# A signer receives the outbound httpx.Request and may add auth headers.
RequestSigner = Callable[[httpx.Request], None]

_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


@dataclass
class PutResult:
    status_code: int = 0
    etag: str = ""


@dataclass
class GetResult:
    status_code: int = 0
    body: bytes = b""
    content_type: str = ""
    etag: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    last_modified: Optional[datetime] = None


@dataclass
class HeadResult:
    status_code: int = 0
    exists: bool = False
    content_type: str = ""
    etag: str = ""
    content_length: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ObjectInfo:
    key: str = ""
    size: int = 0
    etag: str = ""
    last_modified: Optional[datetime] = None


@dataclass
class ListResult:
    status_code: int = 0
    is_truncated: bool = False
    objects: list[ObjectInfo] = field(default_factory=list)


@dataclass
class DeleteResult:
    status_code: int = 0


class S3Error(Exception):
    """Raised when an S3 operation returns a non-2xx status."""


class Client:
    """Path-style S3 test client bound to a fixed endpoint.

    ``endpoint`` is the prefix buckets hang off, e.g.
    ``http://localhost:18770/s3`` — an object lives at
    ``<endpoint>/<bucket>/<key>``.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        http_client: Optional[httpx.Client] = None,
        signer: Optional[RequestSigner] = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._http = http_client or httpx.Client(timeout=30.0)
        self._owns_http = http_client is None
        self._signer = signer

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ── operations ────────────────────────────────────────────────────

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "",
        metadata: Optional[dict[str, str]] = None,
    ) -> PutResult:
        headers: dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = content_type
        for k, v in (metadata or {}).items():
            headers["x-amz-meta-" + k] = v
        resp = self._send("PUT", bucket, key, content=body, headers=headers)
        res = PutResult(status_code=resp.status_code, etag=_etag(resp))
        if resp.status_code >= 300:
            raise self._error("put_object", resp)
        return res

    def get_object(self, bucket: str, key: str) -> GetResult:
        resp = self._send("GET", bucket, key)
        res = GetResult(
            status_code=resp.status_code,
            content_type=resp.headers.get("Content-Type", ""),
            etag=_etag(resp),
            metadata=_extract_meta(resp.headers),
            last_modified=_parse_http_date(resp.headers.get("Last-Modified")),
        )
        if resp.status_code >= 300:
            raise self._error("get_object", resp)
        res.body = resp.content
        return res

    def head_object(self, bucket: str, key: str) -> HeadResult:
        """Fetch object metadata. A 404 is NOT an error — ``exists`` is
        set False so negative tests can assert absence."""
        resp = self._send("HEAD", bucket, key)
        return HeadResult(
            status_code=resp.status_code,
            exists=200 <= resp.status_code < 300,
            content_type=resp.headers.get("Content-Type", ""),
            etag=_etag(resp),
            content_length=int(resp.headers.get("Content-Length", "0") or 0),
            metadata=_extract_meta(resp.headers),
        )

    def list_objects(self, bucket: str, prefix: str = "") -> ListResult:
        params = {"list-type": "2"}
        if prefix:
            params["prefix"] = prefix
        resp = self._send("GET", bucket, "", params=params)
        res = ListResult(status_code=resp.status_code)
        if resp.status_code >= 300:
            raise self._error("list_objects", resp)
        res.is_truncated, res.objects = _parse_listing(resp.content)
        return res

    def delete_object(self, bucket: str, key: str) -> DeleteResult:
        resp = self._send("DELETE", bucket, key)
        if resp.status_code >= 300:
            raise self._error("delete_object", resp)
        return DeleteResult(status_code=resp.status_code)

    # ── internals ─────────────────────────────────────────────────────

    def _send(
        self,
        method: str,
        bucket: str,
        key: str,
        *,
        content: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        if not bucket:
            raise ValueError("mockarty s3: empty bucket")
        url = f"{self._endpoint}/{bucket}/"
        if key:
            url = f"{self._endpoint}/{bucket}/{key.lstrip('/')}"
        req = self._http.build_request(
            method, url, content=content, headers=headers, params=params
        )
        if self._signer is not None:
            self._signer(req)
        return self._http.send(req)

    def _error(self, op: str, resp: httpx.Response) -> S3Error:
        code, message = _parse_error(resp.content)
        if code:
            return S3Error(
                f"mockarty s3: {op}: {code} ({resp.status_code}): {message}"
            )
        return S3Error(f"mockarty s3: {op}: status {resp.status_code}")


# ── helpers ───────────────────────────────────────────────────────────


def _etag(resp: httpx.Response) -> str:
    return resp.headers.get("ETag", "").strip('"')


def _extract_meta(headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk.startswith("x-amz-meta-"):
            out[lk[len("x-amz-meta-") :]] = v
    return out


def _parse_http_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _local_name(tag: str) -> str:
    # Strip an optional ``{namespace}`` prefix so parsing works whether
    # or not the engine emits the S3 XML namespace.
    return tag.rsplit("}", 1)[-1]


def _parse_listing(content: bytes) -> tuple[bool, list[ObjectInfo]]:
    root = ET.fromstring(content)
    is_truncated = False
    objects: list[ObjectInfo] = []
    for child in root:
        name = _local_name(child.tag)
        if name == "IsTruncated":
            is_truncated = (child.text or "").strip().lower() == "true"
        elif name == "Contents":
            info = ObjectInfo()
            for el in child:
                en = _local_name(el.tag)
                text = (el.text or "").strip()
                if en == "Key":
                    info.key = text
                elif en == "Size":
                    info.size = int(text or 0)
                elif en == "ETag":
                    info.etag = text.strip('"')
                elif en == "LastModified":
                    try:
                        info.last_modified = datetime.fromisoformat(
                            text.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
            objects.append(info)
    return is_truncated, objects


def _parse_error(content: bytes) -> tuple[str, str]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return "", ""
    if _local_name(root.tag) != "Error":
        return "", ""
    code = ""
    message = ""
    for el in root:
        name = _local_name(el.tag)
        if name == "Code":
            code = (el.text or "").strip()
        elif name == "Message":
            message = (el.text or "").strip()
    return code, message
