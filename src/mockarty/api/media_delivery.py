"""Operator reconciliation for media jobs with ambiguous runner delivery."""

from __future__ import annotations

from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _base(engine: str) -> str:
    if engine not in ("transcribe", "tts"):
        raise ValueError("media delivery engine must be 'transcribe' or 'tts'")
    return f"/api/v1/{engine}/jobs"


def _payload(runner_id: str, outcome: str) -> dict[str, str]:
    if not runner_id or not runner_id.strip():
        raise ValueError("media delivery runner_id is required")
    if outcome not in ("not_started", "started"):
        raise ValueError("media delivery outcome must be 'not_started' or 'started'")
    return {"runnerId": runner_id, "outcome": outcome}


class MediaDeliveryAPI(SyncAPIBase):
    def list_fenced(self, engine: str) -> dict:
        return self._request("GET", _base(engine) + "/fenced", params={"namespace": self._namespace}).json()

    def reconcile(self, engine: str, job_id: str, runner_id: str, outcome: str) -> None:
        if not job_id or not job_id.strip():
            raise ValueError("media delivery job_id is required")
        self._request(
            "POST",
            _base(engine) + "/" + quote(job_id, safe="") + "/reconcile-delivery",
            params={"namespace": self._namespace},
            json=_payload(runner_id, outcome),
        )


class AsyncMediaDeliveryAPI(AsyncAPIBase):
    async def list_fenced(self, engine: str) -> dict:
        return (await self._request("GET", _base(engine) + "/fenced", params={"namespace": self._namespace})).json()

    async def reconcile(self, engine: str, job_id: str, runner_id: str, outcome: str) -> None:
        if not job_id or not job_id.strip():
            raise ValueError("media delivery job_id is required")
        await self._request(
            "POST",
            _base(engine) + "/" + quote(job_id, safe="") + "/reconcile-delivery",
            params={"namespace": self._namespace},
            json=_payload(runner_id, outcome),
        )
