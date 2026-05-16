# Copyright (c) 2026 Mockarty. All rights reserved.

"""Result + Finding dataclasses returned by the runner.

These are thin parsing wrappers around what the server's
``/api/v1/fuzzing/results/{id}`` and ``/api/v1/fuzzing/findings``
endpoints return. We keep them as plain ``@dataclass`` (not pydantic)
because the runner doesn't need validation — the server is the source
of truth and any drift would only surface as a missing-attribute
error, which we'd rather catch in the user's test than silently
coerce away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Finding:
    """A single fuzz finding — crash / hang / assertion failure / vuln."""

    id: str = ""
    run_id: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    severity: str = ""
    request_method: str = ""
    request_url: str = ""
    request_body: str = ""
    response_status: int = 0
    response_time_ms: int = 0
    response_body: str = ""
    mutation_applied: str = ""
    original_seed_id: str = ""
    reproduce_count: int = 0
    triaged_status: str = ""
    reproducible: Optional[bool] = None
    request_headers: Dict[str, Any] = field(default_factory=dict)
    response_headers: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        """Parse a server payload into a :class:`Finding`. Unknown keys
        are preserved under ``raw`` for forward-compat.
        """

        return cls(
            id=str(data.get("id", "")),
            run_id=str(data.get("runId", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            category=str(data.get("category", "")),
            severity=str(data.get("severity", "")),
            request_method=str(data.get("requestMethod", "")),
            request_url=str(data.get("requestUrl", "")),
            request_body=str(data.get("requestBody", "")),
            response_status=int(data.get("responseStatus", 0) or 0),
            response_time_ms=int(data.get("responseTimeMs", 0) or 0),
            response_body=str(data.get("responseBody", "")),
            mutation_applied=str(data.get("mutationApplied", "")),
            original_seed_id=str(data.get("originalSeedId", "")),
            reproduce_count=int(data.get("reproduceCount", 0) or 0),
            triaged_status=str(data.get("triagedStatus", "")),
            reproducible=data.get("reproducible"),
            request_headers=data.get("requestHeaders") or {},
            response_headers=data.get("responseHeaders") or {},
            raw=dict(data),
        )

    @property
    def is_crash(self) -> bool:
        return self.category in {"500_error", "timeout", "empty_response"}

    @property
    def is_security(self) -> bool:
        return self.category in {
            "sqli",
            "xss",
            "command_injection",
            "path_traversal",
            "ssrf",
            "xxe",
            "ssti",
            "auth_bypass",
            "nosql_injection",
            "ldap_injection",
            "xpath_injection",
            "orm_injection",
            "jwt_none_alg",
            "jwt_weak_secret",
            "insecure_deserialization",
            "open_redirect",
            "http_request_smuggling",
            "idor",
        }


@dataclass
class Result:
    """Run-level summary returned by the runner."""

    id: str = ""
    config_id: str = ""
    config_name: str = ""
    namespace: str = ""
    status: str = ""
    strategy: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    total_requests: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    info_findings: int = 0
    network_error_count: int = 0
    findings: List[Finding] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Result":
        def _parse_dt(v: Any) -> Optional[datetime]:
            if v is None or v == "":
                return None
            try:
                return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            except ValueError:
                return None

        findings_in = data.get("findings") or []
        return cls(
            id=str(data.get("id", "")),
            config_id=str(data.get("configId", "") or ""),
            config_name=str(data.get("configName", "")),
            namespace=str(data.get("namespace", "")),
            status=str(data.get("status", "")),
            strategy=str(data.get("strategy", "")),
            started_at=_parse_dt(data.get("startedAt")),
            completed_at=_parse_dt(data.get("completedAt")),
            duration_ms=int(data.get("durationMs", 0) or 0),
            total_requests=int(data.get("totalRequests", 0) or 0),
            total_findings=int(data.get("totalFindings", 0) or 0),
            critical_findings=int(data.get("criticalFindings", 0) or 0),
            high_findings=int(data.get("highFindings", 0) or 0),
            medium_findings=int(data.get("mediumFindings", 0) or 0),
            low_findings=int(data.get("lowFindings", 0) or 0),
            info_findings=int(data.get("infoFindings", 0) or 0),
            network_error_count=int(data.get("networkErrorCount", 0) or 0),
            findings=[Finding.from_dict(f) for f in findings_in if isinstance(f, dict)],
            raw=dict(data),
        )

    @property
    def passed(self) -> bool:
        """True when the run completed with no critical/high findings."""

        return (
            self.status in {"completed", "success", "passed"}
            and self.critical_findings == 0
            and self.high_findings == 0
        )

    @property
    def failed(self) -> bool:
        return not self.passed
