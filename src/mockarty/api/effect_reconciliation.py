"""Admin queue for unresolved external effects."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase

_QUEUE_PATH = "/api/v1/admin/effects/reconciliation"
_RECONCILE_PATH = _QUEUE_PATH + "/reconcile"


def _list_params(namespace: str, *, project_id: str = "", effect_family: str = "", reason: str = "", min_age_seconds: int = 0, limit: int = 50, cursor: str = "") -> dict:
    if min_age_seconds < 0 or min_age_seconds > 7_776_000:
        raise ValueError("effect reconciliation min_age_seconds must be between 0 and 7776000")
    if limit < 1 or limit > 100:
        raise ValueError("effect reconciliation limit must be between 1 and 100")
    params = {"namespace": namespace, "minAgeSeconds": min_age_seconds, "limit": limit}
    for key, value in (("project", project_id), ("family", effect_family), ("reason", reason), ("cursor", cursor)):
        if value:
            params[key] = value
    return params


def _reconcile_payload(namespace: str, execution_id: str, provider_reference: str, evidence_source: str) -> dict:
    execution_id = execution_id.strip()
    if not execution_id:
        raise ValueError("effect reconciliation execution_id is required")
    return {
        "namespace": namespace,
        "executionId": execution_id,
        "decision": "no_effect",
        "autoClaim": True,
        "providerReference": provider_reference.strip(),
        "evidenceSource": evidence_source.strip(),
    }


class EffectReconciliationAPI(SyncAPIBase):
    def list_queue(self, *, project_id: str = "", effect_family: str = "", reason: str = "", min_age_seconds: int = 0, limit: int = 50, cursor: str = "") -> dict:
        return self._request("GET", _QUEUE_PATH, params=_list_params(self._namespace, project_id=project_id, effect_family=effect_family, reason=reason, min_age_seconds=min_age_seconds, limit=limit, cursor=cursor)).json()

    def reconcile_no_effect(self, execution_id: str, provider_reference: str = "", evidence_source: str = "") -> dict:
        return self._request("POST", _RECONCILE_PATH, json=_reconcile_payload(self._namespace, execution_id, provider_reference, evidence_source)).json()


class AsyncEffectReconciliationAPI(AsyncAPIBase):
    async def list_queue(self, *, project_id: str = "", effect_family: str = "", reason: str = "", min_age_seconds: int = 0, limit: int = 50, cursor: str = "") -> dict:
        response = await self._request("GET", _QUEUE_PATH, params=_list_params(self._namespace, project_id=project_id, effect_family=effect_family, reason=reason, min_age_seconds=min_age_seconds, limit=limit, cursor=cursor))
        return response.json()

    async def reconcile_no_effect(self, execution_id: str, provider_reference: str = "", evidence_source: str = "") -> dict:
        response = await self._request("POST", _RECONCILE_PATH, json=_reconcile_payload(self._namespace, execution_id, provider_reference, evidence_source))
        return response.json()
