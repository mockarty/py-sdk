# Copyright (c) 2026 Mockarty. All rights reserved.

"""Recorder API resource for traffic recording sessions."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.mock import Mock
from mockarty.models.recorder import RecorderEntry, RecorderSession


class RecorderAPI(SyncAPIBase):
    """Synchronous Recorder API resource."""

    def create(self, session: RecorderSession | dict[str, Any]) -> RecorderSession:
        """Create and start a new recording session."""
        resp = self._request("POST", "/api/v1/recorder/start", json=session)
        return RecorderSession.model_validate(resp.json())

    def list(self) -> list[RecorderSession]:
        """List all recording sessions."""
        resp = self._request("GET", "/api/v1/recorder/sessions")
        data = resp.json()
        if isinstance(data, list):
            return [RecorderSession.model_validate(s) for s in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("sessions") or []
            return [RecorderSession.model_validate(s) for s in items]
        return []

    def get(self, session_id: str) -> RecorderSession:
        """Get a recording session by ID."""
        resp = self._request("GET", f"/api/v1/recorder/{session_id}")
        return RecorderSession.model_validate(resp.json())

    def stop(self, session_id: str) -> RecorderSession:
        """Stop recording traffic for a session."""
        resp = self._request("POST", f"/api/v1/recorder/{session_id}/stop")
        return RecorderSession.model_validate(resp.json())

    def delete(self, session_id: str) -> None:
        """Delete a recording session."""
        self._request("DELETE", f"/api/v1/recorder/{session_id}")

    def entries(self, session_id: str) -> list[RecorderEntry]:
        """List recorded entries for a session."""
        resp = self._request("GET", f"/api/v1/recorder/{session_id}/entries")
        data = resp.json()
        if isinstance(data, list):
            return [RecorderEntry.model_validate(e) for e in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("entries") or []
            return [RecorderEntry.model_validate(e) for e in items]
        return []

    def generate_mocks(self, session_id: str) -> list[Mock]:
        """Generate mocks from recorded traffic."""
        resp = self._request("POST", f"/api/v1/recorder/{session_id}/mocks")
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        if isinstance(data, dict):
            items = data.get("mocks") or data.get("items") or []
            return [Mock.model_validate(m) for m in items]
        return []

    # ── Configs ────────────────────────────────────────────────────────

    def list_configs(self) -> list[dict[str, Any]]:
        """List all recorder configurations."""
        resp = self._request("GET", "/api/v1/recorder/configs")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("configs") or []
        return []

    def save_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Save a recorder configuration."""
        resp = self._request("POST", "/api/v1/recorder/configs", json=config)
        return resp.json()

    def delete_config(self, config_id: str) -> None:
        """Delete a recorder configuration."""
        self._request("DELETE", f"/api/v1/recorder/configs/{config_id}")

    def export_config(self, config_id: str) -> bytes:
        """Export a recorder configuration as raw bytes."""
        resp = self._request("GET", f"/api/v1/recorder/configs/{config_id}/export")
        return resp.content

    # ── CA (Certificate Authority) ─────────────────────────────────────

    def get_ca_status(self) -> dict[str, Any]:
        """Get the CA certificate status."""
        resp = self._request("GET", "/api/v1/recorder/ca/status")
        return resp.json()

    def generate_ca(self) -> dict[str, Any]:
        """Generate a new CA certificate."""
        resp = self._request("POST", "/api/v1/recorder/ca/generate")
        return resp.json()

    def download_ca(self) -> bytes:
        """Download the CA certificate."""
        resp = self._request("GET", "/api/v1/recorder/ca/download")
        return resp.content

    # ── Advanced entry operations ──────────────────────────────────────

    def annotate_entry(
        self,
        session_id: str,
        entry_id: str,
        annotation: dict[str, Any],
    ) -> dict[str, Any]:
        """Annotate a recorded entry."""
        resp = self._request(
            "PATCH",
            f"/api/v1/recorder/{session_id}/entries/{entry_id}",
            json=annotation,
        )
        return resp.json()

    def replay_entry(self, session_id: str, entry_id: str) -> dict[str, Any]:
        """Replay a recorded entry against the target."""
        resp = self._request(
            "POST",
            f"/api/v1/recorder/{session_id}/entries/{entry_id}/replay",
        )
        return resp.json()

    # ── Session-level replay & correlation ─────────────────────────────

    def replay_session(
        self,
        session_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Replay every (or selected) captured entry against a target.

        Re-runs entries against either their original URL or a different
        target (e.g. point a production capture at staging) and returns a
        summary with match/mismatch/fail/skip counts.

        Options keys (all optional):
            targetUrl (str):       base URL to replay against; defaults to original
            concurrency (int):     parallel replay workers (default 1)
            timeoutMs (int):       per-request timeout in ms (0 = server default)
            entryIds (list[str]):  replay only these entry IDs
            includeNonHttp (bool): include WS/SSE entries
            followRedirects (bool): follow HTTP redirects during replay
        """
        body = options or {}
        resp = self._request(
            "POST",
            f"/api/v1/recorder/{session_id}/replay",
            json=body,
        )
        return resp.json()

    def correlate_session(
        self,
        session_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Discover dynamic-value flow between captured entries.

        Runs the deterministic value-matching correlation engine: scans
        each entry's response (JSON, headers, Set-Cookie) for values that
        are then re-used in a later entry's request (URL, header, body,
        form, cookie). The output highlights tokens, IDs, and CSRF values
        that need to be extracted at runtime.

        Options keys (all optional):
            minValueLength (int):           minimum value length to consider
            maxValueLength (int):           maximum value length
            excludeNumeric (bool):          skip numeric-only values
            maxCorrelationsPerSource (int): cap targets per source value
            entryIds (list[str]):           limit scan to these entry IDs
        """
        body = options or {}
        resp = self._request(
            "POST",
            f"/api/v1/recorder/{session_id}/correlate",
            json=body,
        )
        return resp.json()

    # ── Modifications ──────────────────────────────────────────────────

    def get_modifications(self, session_id: str) -> dict[str, Any]:
        """Get traffic modifications for a session."""
        resp = self._request("GET", f"/api/v1/recorder/{session_id}/modifications")
        return resp.json()

    def update_modifications(
        self, session_id: str, modifications: dict[str, Any]
    ) -> dict[str, Any]:
        """Update traffic modifications for a session."""
        resp = self._request(
            "PUT",
            f"/api/v1/recorder/{session_id}/modifications",
            json=modifications,
        )
        return resp.json()

    # ── Ports ──────────────────────────────────────────────────────────

    def get_ports(self) -> dict[str, Any]:
        """Get recorder port allocation status."""
        resp = self._request("GET", "/api/v1/recorder/ports")
        return resp.json()


class AsyncRecorderAPI(AsyncAPIBase):
    """Asynchronous Recorder API resource."""

    async def create(
        self, session: RecorderSession | dict[str, Any]
    ) -> RecorderSession:
        """Create and start a new recording session."""
        resp = await self._request("POST", "/api/v1/recorder/start", json=session)
        return RecorderSession.model_validate(resp.json())

    async def list(self) -> list[RecorderSession]:
        """List all recording sessions."""
        resp = await self._request("GET", "/api/v1/recorder/sessions")
        data = resp.json()
        if isinstance(data, list):
            return [RecorderSession.model_validate(s) for s in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("sessions") or []
            return [RecorderSession.model_validate(s) for s in items]
        return []

    async def get(self, session_id: str) -> RecorderSession:
        """Get a recording session by ID."""
        resp = await self._request("GET", f"/api/v1/recorder/{session_id}")
        return RecorderSession.model_validate(resp.json())

    async def stop(self, session_id: str) -> RecorderSession:
        """Stop recording traffic for a session."""
        resp = await self._request("POST", f"/api/v1/recorder/{session_id}/stop")
        return RecorderSession.model_validate(resp.json())

    async def delete(self, session_id: str) -> None:
        """Delete a recording session."""
        await self._request("DELETE", f"/api/v1/recorder/{session_id}")

    async def entries(self, session_id: str) -> list[RecorderEntry]:
        """List recorded entries for a session."""
        resp = await self._request("GET", f"/api/v1/recorder/{session_id}/entries")
        data = resp.json()
        if isinstance(data, list):
            return [RecorderEntry.model_validate(e) for e in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("entries") or []
            return [RecorderEntry.model_validate(e) for e in items]
        return []

    async def generate_mocks(self, session_id: str) -> list[Mock]:
        """Generate mocks from recorded traffic."""
        resp = await self._request("POST", f"/api/v1/recorder/{session_id}/mocks")
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        if isinstance(data, dict):
            items = data.get("mocks") or data.get("items") or []
            return [Mock.model_validate(m) for m in items]
        return []

    # ── Configs ────────────────────────────────────────────────────────

    async def list_configs(self) -> list[dict[str, Any]]:
        """List all recorder configurations."""
        resp = await self._request("GET", "/api/v1/recorder/configs")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("configs") or []
        return []

    async def save_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Save a recorder configuration."""
        resp = await self._request("POST", "/api/v1/recorder/configs", json=config)
        return resp.json()

    async def delete_config(self, config_id: str) -> None:
        """Delete a recorder configuration."""
        await self._request("DELETE", f"/api/v1/recorder/configs/{config_id}")

    async def export_config(self, config_id: str) -> bytes:
        """Export a recorder configuration as raw bytes."""
        resp = await self._request(
            "GET", f"/api/v1/recorder/configs/{config_id}/export"
        )
        return resp.content

    # ── CA (Certificate Authority) ─────────────────────────────────────

    async def get_ca_status(self) -> dict[str, Any]:
        """Get the CA certificate status."""
        resp = await self._request("GET", "/api/v1/recorder/ca/status")
        return resp.json()

    async def generate_ca(self) -> dict[str, Any]:
        """Generate a new CA certificate."""
        resp = await self._request("POST", "/api/v1/recorder/ca/generate")
        return resp.json()

    async def download_ca(self) -> bytes:
        """Download the CA certificate."""
        resp = await self._request("GET", "/api/v1/recorder/ca/download")
        return resp.content

    # ── Advanced entry operations ──────────────────────────────────────

    async def annotate_entry(
        self,
        session_id: str,
        entry_id: str,
        annotation: dict[str, Any],
    ) -> dict[str, Any]:
        """Annotate a recorded entry."""
        resp = await self._request(
            "PATCH",
            f"/api/v1/recorder/{session_id}/entries/{entry_id}",
            json=annotation,
        )
        return resp.json()

    async def replay_entry(self, session_id: str, entry_id: str) -> dict[str, Any]:
        """Replay a recorded entry against the target."""
        resp = await self._request(
            "POST",
            f"/api/v1/recorder/{session_id}/entries/{entry_id}/replay",
        )
        return resp.json()

    # ── Session-level replay & correlation ─────────────────────────────

    async def replay_session(
        self,
        session_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Replay every (or selected) captured entry against a target.

        See ``RecorderAPI.replay_session`` for the options dict shape.
        """
        body = options or {}
        resp = await self._request(
            "POST",
            f"/api/v1/recorder/{session_id}/replay",
            json=body,
        )
        return resp.json()

    async def correlate_session(
        self,
        session_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Discover dynamic-value flow between captured entries.

        See ``RecorderAPI.correlate_session`` for the options dict shape.
        """
        body = options or {}
        resp = await self._request(
            "POST",
            f"/api/v1/recorder/{session_id}/correlate",
            json=body,
        )
        return resp.json()

    # ── Modifications ──────────────────────────────────────────────────

    async def get_modifications(self, session_id: str) -> dict[str, Any]:
        """Get traffic modifications for a session."""
        resp = await self._request(
            "GET", f"/api/v1/recorder/{session_id}/modifications"
        )
        return resp.json()

    async def update_modifications(
        self, session_id: str, modifications: dict[str, Any]
    ) -> dict[str, Any]:
        """Update traffic modifications for a session."""
        resp = await self._request(
            "PUT",
            f"/api/v1/recorder/{session_id}/modifications",
            json=modifications,
        )
        return resp.json()

    # ── Ports ──────────────────────────────────────────────────────────

    async def get_ports(self) -> dict[str, Any]:
        """Get recorder port allocation status."""
        resp = await self._request("GET", "/api/v1/recorder/ports")
        return resp.json()
