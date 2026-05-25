# Copyright (c) 2026 Mockarty. All rights reserved.

"""Security Agent API resource — CI/CD-useful subset.

Exposes the operator-friendly surface of the Mockarty Security Agent
(``/api/v1/security/*``): start a scan, poll status, list findings,
download SARIF, list scanners, cancel a scan. Admin operations — LLM
profile CRUD, remote-agent on/off, scanner-template editing — live in
the admin UI and are intentionally NOT in the SDK.

The server gates every route behind the ``security_agent`` feature
flag; a 403 from any of these calls means the namespace lacks the
licence feature.
"""

from __future__ import annotations

from typing import Any

from mockarty.api._base import SyncAPIBase


class SecurityAPI(SyncAPIBase):
    """Synchronous Security Agent API resource."""

    # ── Scans ────────────────────────────────────────────────────────

    def start_scan(
        self,
        namespace: str,
        target: str,
        persona: str = "web_pentester",
        intensity: str = "passive",
        title: str | None = None,
        max_cost_usd_micros: int = 0,
        scope_description: str = "",
        extra_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start an orchestrated security scan and return the new report row.

        POST /api/v1/security/scans

        Args:
            namespace: target Mockarty namespace.
            target: URL or host:port to scan.
            persona: pentest persona (``web_pentester``, ``api_pentester``,
                ``infra_pentester``, ``mobile_pentester``, ``cloud_pentester``).
                Currently informational — the server's orchestrator picks
                applicable scanners based on the targets, not the persona name.
            intensity: one of ``passive`` | ``safe-active`` | ``intrusive``
                | ``destructive``. Use ``passive`` for routine CI.
            title: human label for the report (default: derived from target).
            max_cost_usd_micros: per-run LLM cost ceiling in USD micros
                (1 USD = 1_000_000). 0 = unlimited (NOT recommended for CI).
            scope_description: free-text scope; conveyed to planner LLM.
            extra_profile: additional ScanProfile fields to merge in.
        """
        profile: dict[str, Any] = {
            "intensity": intensity,
            "scopeDescription": scope_description or target,
            "targets": [{"url": target, "method": "GET"}],
            "redactTokensInReport": True,
        }
        if max_cost_usd_micros:
            profile["maxCostUsdMicros"] = max_cost_usd_micros
        if extra_profile:
            profile.update(extra_profile)

        body = {
            "title": title or f"sdk-{persona}-{target}",
            "namespace": namespace,
            "profile": profile,
        }
        resp = self._request("POST", "/api/v1/security/scans", json=body)
        data = resp.json()
        if isinstance(data, dict):
            return data.get("report") or data
        return {}

    def get_report(self, report_id: str) -> dict[str, Any]:
        """Return the current state of a scan report.

        GET /api/v1/security/reports/:id
        """
        resp = self._request("GET", f"/api/v1/security/reports/{report_id}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("report") or data
        return {}

    def cancel_scan(self, report_id: str) -> None:
        """Signal an in-flight scan to wind down.

        POST /api/v1/security/reports/:id/cancel
        """
        self._request("POST", f"/api/v1/security/reports/{report_id}/cancel")

    # ── Findings ─────────────────────────────────────────────────────

    def list_findings(
        self,
        report_id: str,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return every finding recorded against the report.

        GET /api/v1/security/reports/:id/findings

        ``severity`` filters client-side to keep the SDK shape stable —
        the server does not (yet) support a ``severity`` query param.
        """
        resp = self._request("GET", f"/api/v1/security/reports/{report_id}/findings")
        data = resp.json()
        findings: list[dict[str, Any]] = []
        if isinstance(data, dict):
            raw = data.get("findings") or []
            if isinstance(raw, list):
                findings = [f for f in raw if isinstance(f, dict)]
        if not severity:
            return findings
        wanted = severity.strip().lower()
        return [f for f in findings if str(f.get("severity", "")).lower() == wanted]

    # ── Exports ──────────────────────────────────────────────────────

    def export_report(self, report_id: str, format: str = "sarif") -> bytes:
        """Download the report serialised in ``format``.

        GET /api/v1/security/reports/:id/export?format=<format>

        Supported formats: ``sarif`` | ``vex`` | ``html`` | ``pdf`` |
        ``allure``. Returns raw bytes; caller persists them.
        """
        fmt = (format or "sarif").strip().lower()
        if fmt not in {"sarif", "vex", "cyclonedx", "cyclonedx-vex", "html", "pdf", "allure"}:
            raise ValueError(
                f"unsupported export format {format!r} "
                "(want one of sarif|vex|html|pdf|allure)"
            )
        resp = self._request(
            "GET",
            f"/api/v1/security/reports/{report_id}/export",
            params={"format": fmt},
        )
        return resp.content

    # ── Catalogue ────────────────────────────────────────────────────

    def list_scanners(self) -> list[dict[str, Any]]:
        """Enumerate registered scan providers (key, persona, intensity).

        GET /api/v1/security/scanners
        """
        resp = self._request("GET", "/api/v1/security/scanners")
        data = resp.json()
        if isinstance(data, dict):
            raw = data.get("scanners") or []
            if isinstance(raw, list):
                return [s for s in raw if isinstance(s, dict)]
        return []
