# Copyright (c) 2026 Mockarty. All rights reserved.

"""Pact Broker client — publish, fetch, can-i-deploy.

Mirrors the Go SDK ``mockartygo/pact.BrokerClient`` surface so a
multi-language CI can use whichever SDK fits the build system.

Env vars (same as pact-broker CLI + pact-foundation libraries so
existing CI scripts keep working):

* ``PACT_BROKER_BASE_URL`` — broker URL (required)
* ``PACT_BROKER_TOKEN``    — bearer token (preferred)
* ``PACT_BROKER_USERNAME`` / ``PACT_BROKER_PASSWORD`` — basic auth fallback

Bearer wins over basic when both are set.

Quick start::

    from mockarty.pact.broker import BrokerClient

    client = BrokerClient()  # picks up env
    pact_bytes = open("pacts/OrderClient-OrderAPI.json", "rb").read()
    client.publish(pact_bytes, consumer_version="1.2.3", branch="main",
                   tags=["ci"])
    res = client.can_i_deploy("OrderClient", "1.2.3", to_environment="prod")
    if not res.deployable:
        raise SystemExit(f"BLOCKED: {res.reason}")
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

try:  # urllib3 is a transitive dep via requests
    import urllib3
except ImportError as e:  # pragma: no cover
    raise ImportError("mockarty.pact.broker requires urllib3") from e


class PactNotFoundError(LookupError):
    """Raised when GET on a non-existent pact returns 404."""


class BrokerError(RuntimeError):
    """Broker HTTP error with status + body for CI surfaces."""

    def __init__(self, status: int, body: str, message: str = "") -> None:
        super().__init__(message or f"pact broker HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


@dataclasses.dataclass(frozen=True)
class CanIDeployResult:
    """Result of GET /can-i-deploy."""

    deployable: bool
    reason: str
    raw: bytes


class BrokerClient:
    """Pact Broker HTTP client.

    Bearer token wins over basic auth when both are configured —
    matches the Go SDK + pact-foundation tooling.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
        pool: urllib3.PoolManager | None = None,
    ) -> None:
        url = (base_url if base_url is not None else os.getenv("PACT_BROKER_BASE_URL", "")).strip()
        if not url:
            raise ValueError(
                "BrokerClient requires base_url or PACT_BROKER_BASE_URL env var"
            )
        self.base_url = url.rstrip("/")
        self.token = (token if token is not None else os.getenv("PACT_BROKER_TOKEN", "")).strip()
        self.username = (
            username if username is not None else os.getenv("PACT_BROKER_USERNAME", "")
        ).strip()
        self.password = (
            password if password is not None else os.getenv("PACT_BROKER_PASSWORD", "")
        ).strip()
        self.timeout = timeout
        self._pool = pool or urllib3.PoolManager()

    def auth_headers(self) -> dict[str, str]:
        """Auth headers (Bearer or Basic, per pact-foundation precedence).

        Public so sibling components (e.g. the verifier publishing
        results back to the same broker) can reuse this client's
        credentials without reaching into private state.
        """
        return self._auth_headers()

    def _auth_headers(self) -> dict[str, str]:
        # RFC 6749 + pact-foundation precedence: bearer wins over basic.
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        if self.username or self.password:
            import base64

            cred = f"{self.username}:{self.password}".encode()
            return {"Authorization": "Basic " + base64.b64encode(cred).decode()}
        return {}

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        accept_404: bool = False,
    ) -> urllib3.HTTPResponse:
        url = self.base_url + path
        hdrs = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self._auth_headers(),
            **(headers or {}),
        }
        resp = self._pool.request(
            method,
            url,
            body=body,
            headers=hdrs,
            timeout=self.timeout,
            redirect=False,
        )
        if resp.status == 404 and accept_404:
            return resp
        if resp.status >= 400:
            raise BrokerError(resp.status, _safe_body(resp))
        return resp

    # ------------------------------------------------------------------
    # publish / fetch
    # ------------------------------------------------------------------

    def publish(
        self,
        pact_bytes: bytes,
        consumer_version: str,
        branch: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """Publish a pact JSON document to the broker.

        Raises:
            ValueError: malformed pact JSON or missing consumer.name /
                provider.name / consumer_version.
            BrokerError: broker rejected the publish (4xx/5xx).
        """
        if not consumer_version.strip():
            raise ValueError("consumer_version is required")
        consumer, provider = _extract_consumer_provider(pact_bytes)
        path = (
            f"/pacts/provider/{_quote(provider)}"
            f"/consumer/{_quote(consumer)}/version/{_quote(consumer_version)}"
        )
        hdrs: dict[str, str] = {}
        if branch:
            hdrs["X-Pact-Consumer-Branch"] = branch
        self._request("PUT", path, body=pact_bytes, headers=hdrs)
        for tag in tags or []:
            tag = tag.strip()
            if not tag:
                continue
            tag_path = (
                f"/pacticipants/{_quote(consumer)}"
                f"/versions/{_quote(consumer_version)}/tags/{_quote(tag)}"
            )
            self._request("PUT", tag_path, body=b"")

    def fetch(self, consumer: str, provider: str, version: str) -> bytes:
        """Fetch a specific pact version.

        Raises:
            PactNotFoundError: 404 on the resource.
        """
        path = (
            f"/pacts/provider/{_quote(provider)}"
            f"/consumer/{_quote(consumer)}/version/{_quote(version)}"
        )
        resp = self._request("GET", path, accept_404=True)
        if resp.status == 404:
            raise PactNotFoundError(f"{consumer}/{provider}/{version}")
        return resp.data

    def fetch_latest(self, consumer: str, provider: str) -> bytes:
        """Fetch the latest published version of a consumer pact."""
        return self.fetch(consumer, provider, "latest")

    def can_i_deploy(
        self,
        pacticipant: str,
        version: str,
        to_environment: str = "",
    ) -> CanIDeployResult:
        """GET /can-i-deploy — gate before deploying a build.

        ``to_environment`` is optional; omit for the simpler
        ``latest`` matrix check. Returns ``deployable=False`` with a
        non-empty ``reason`` when the broker says no.
        """
        if not pacticipant.strip():
            raise ValueError("pacticipant is required")
        if not version.strip():
            raise ValueError("version is required")
        params: list[tuple[str, str]] = [
            ("pacticipant", pacticipant),
            ("version", version),
        ]
        if to_environment:
            params.append(("environment", to_environment))
        query = "&".join(f"{_quote(k)}={_quote(v)}" for k, v in params)
        resp = self._request("GET", f"/can-i-deploy?{query}")
        try:
            payload = json.loads(resp.data.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise BrokerError(
                resp.status, resp.data.decode("utf-8", errors="replace"),
                message=f"can-i-deploy: unparsable JSON ({e})",
            ) from e
        summary = (
            payload.get("summary") if isinstance(payload, dict) else None
        ) or {}
        deployable = bool(summary.get("deployable", False))
        reason = str(summary.get("reason", ""))
        return CanIDeployResult(
            deployable=deployable,
            reason=reason,
            raw=resp.data,
        )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _extract_consumer_provider(raw: bytes) -> tuple[str, str]:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"pact is not valid JSON: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError("pact root must be a JSON object")
    cons = _name_of(doc.get("consumer"))
    prov = _name_of(doc.get("provider"))
    if not cons:
        raise ValueError("pact.consumer.name is required")
    if not prov:
        raise ValueError("pact.provider.name is required")
    return cons, prov


def _name_of(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    name = obj.get("name")
    return name.strip() if isinstance(name, str) else ""


def _quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def _safe_body(resp: urllib3.HTTPResponse) -> str:
    try:
        return resp.data.decode("utf-8")
    except UnicodeDecodeError:
        return resp.data.decode("utf-8", errors="replace")


__all__ = [
    "BrokerClient",
    "BrokerError",
    "CanIDeployResult",
    "PactNotFoundError",
]
