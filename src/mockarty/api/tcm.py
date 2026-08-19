# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Test Case Management (TCM) automation API — cases, case-runs, defects.

Create/read/update/run test cases, poll case-runs, and file defects over
Mockarty's TCM. Cases live under ``/api/v1/namespaces/:ns/test-cases``;
case-runs and defects under ``/api/v1/namespaces/:ns/tcm/...``. Payloads are
rich and evolve, so this API uses loosely-typed dict I/O (mirrored by the Go
map and Java JsonNode SDKs). Every method takes an optional ``namespace``.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from mockarty._base_client import raise_for_status, wrap_transport_error
from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _cases(namespace: str) -> str:
    if not namespace:
        raise ValueError("namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/test-cases"


def _tcm(namespace: str) -> str:
    if not namespace:
        raise ValueError("namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/tcm"


def _clean(params: Optional[dict[str, str]]) -> dict[str, str]:
    return {k: v for k, v in (params or {}).items() if v}


def _array(data: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            if isinstance(data.get(k), list):
                return data[k]
    return []


class TCMAPI(SyncAPIBase):
    """Synchronous TCM API — cases, case-runs, defects."""

    # -- cases --
    def create_case(self, test_case: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Create a test case (fields: ``title``, ``folderId``, ``steps``, …)."""
        ns = namespace or self._namespace
        return self._request("POST", _cases(ns), json=test_case).json()

    def get_case(self, case_id: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return self._request("GET", f"{_cases(ns)}/{quote(case_id, safe='')}").json()

    def list_cases(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        data = self._request("GET", _cases(ns), params=_clean(filters)).json()
        return _array(data, "test_cases", "cases", "items")

    def update_case(self, case_id: str, fields: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return self._request("PUT", f"{_cases(ns)}/{quote(case_id, safe='')}", json=fields).json()

    def delete_case(self, case_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        self._request("DELETE", f"{_cases(ns)}/{quote(case_id, safe='')}")

    def run_case(self, case_id: str, opts: Optional[dict[str, Any]] = None, *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Start a run of a test case; returns the run descriptor (with the run
        id to poll via :meth:`get_case_run`)."""
        ns = namespace or self._namespace
        return self._request("POST", f"{_cases(ns)}/{quote(case_id, safe='')}/run", json=opts or {}).json()

    def list_case_runs(self, case_id: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        data = self._request("GET", f"{_cases(ns)}/{quote(case_id, safe='')}/runs").json()
        return _array(data, "runs", "caseRuns", "case_runs", "items")

    # -- case-runs --
    def get_case_run(self, run_id: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return self._request("GET", f"{_tcm(ns)}/case-runs/{quote(run_id, safe='')}").json()

    def cancel_case_run(self, run_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        self._request("POST", f"{_tcm(ns)}/case-runs/{quote(run_id, safe='')}/cancel")

    # -- defects --
    def create_defect(self, defect: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return self._request("POST", f"{_tcm(ns)}/defects", json=defect).json()

    def list_defects(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        data = self._request("GET", f"{_tcm(ns)}/defects", params=_clean(filters)).json()
        return _array(data, "defects", "items")

    def delete_defect(self, defect_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        self._request("DELETE", f"{_tcm(ns)}/defects/{quote(defect_id, safe='')}")

    # -- folders --
    def get_folder_tree(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        return _array(self._request("GET", f"{_tcm(ns)}/folders/tree").json(), "items")

    def list_folders(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        return _array(self._request("GET", f"{_tcm(ns)}/folders").json(), "items")

    def create_folder(self, folder: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return self._request("POST", f"{_tcm(ns)}/folders", json=folder).json()

    def update_folder(self, folder_id: str, fields: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return self._request("PATCH", f"{_tcm(ns)}/folders/{quote(folder_id, safe='')}", json=fields).json()

    def delete_folder(self, folder_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        self._request("DELETE", f"{_tcm(ns)}/folders/{quote(folder_id, safe='')}")

    def move_folder(self, folder_id: str, to_parent_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        self._request("POST", f"{_tcm(ns)}/folders/{quote(folder_id, safe='')}/move", json={"toParentId": to_parent_id})

    # -- attachments --
    def upload_attachment(self, parent_kind: str, parent_id: str, filename: str, content: bytes,
                          *, media_type: str = "application/octet-stream", namespace: Optional[str] = None) -> dict[str, Any]:
        """Upload an attachment to a (parent_kind, parent_id) — e.g. a video,
        screenshot, log or report attached to a case/run/step."""
        ns = namespace or self._namespace
        url = f"{_tcm(ns)}/attachments/upload"
        try:
            resp = self._client.request("POST", url, params={"parentKind": parent_kind, "parentId": parent_id},
                                        files={"file": (filename, content, media_type)})
        except Exception as exc:  # noqa: BLE001 — normalised below
            wrap_transport_error(exc)
        raise_for_status(resp)
        return resp.json()

    def list_attachments(self, parent_kind: str, parent_id: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = self._request("GET", f"{_tcm(ns)}/attachments", params={"parentKind": parent_kind, "parentId": parent_id})
        return _array(resp.json(), "items", "attachments")

    def download_attachment(self, attachment_id: str, *, namespace: Optional[str] = None) -> bytes:
        ns = namespace or self._namespace
        return self._request("GET", f"{_tcm(ns)}/attachments/{quote(attachment_id, safe='')}/raw").content

    def delete_attachment(self, attachment_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        self._request("DELETE", f"{_tcm(ns)}/attachments/{quote(attachment_id, safe='')}")


class AsyncTCMAPI(AsyncAPIBase):
    """Asynchronous mirror of :class:`TCMAPI`."""

    async def create_case(self, test_case: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", _cases(ns), json=test_case)).json()

    async def get_case(self, case_id: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_cases(ns)}/{quote(case_id, safe='')}")).json()

    async def list_cases(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        data = (await self._request("GET", _cases(ns), params=_clean(filters))).json()
        return _array(data, "test_cases", "cases", "items")

    async def update_case(self, case_id: str, fields: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("PUT", f"{_cases(ns)}/{quote(case_id, safe='')}", json=fields)).json()

    async def delete_case(self, case_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("DELETE", f"{_cases(ns)}/{quote(case_id, safe='')}")

    async def run_case(self, case_id: str, opts: Optional[dict[str, Any]] = None, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_cases(ns)}/{quote(case_id, safe='')}/run", json=opts or {})).json()

    async def list_case_runs(self, case_id: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        data = (await self._request("GET", f"{_cases(ns)}/{quote(case_id, safe='')}/runs")).json()
        return _array(data, "runs", "caseRuns", "case_runs", "items")

    async def get_case_run(self, run_id: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_tcm(ns)}/case-runs/{quote(run_id, safe='')}")).json()

    async def cancel_case_run(self, run_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("POST", f"{_tcm(ns)}/case-runs/{quote(run_id, safe='')}/cancel")

    async def create_defect(self, defect: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_tcm(ns)}/defects", json=defect)).json()

    async def list_defects(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        data = (await self._request("GET", f"{_tcm(ns)}/defects", params=_clean(filters))).json()
        return _array(data, "defects", "items")

    async def delete_defect(self, defect_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("DELETE", f"{_tcm(ns)}/defects/{quote(defect_id, safe='')}")

    # -- folders --
    async def get_folder_tree(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        return _array((await self._request("GET", f"{_tcm(ns)}/folders/tree")).json(), "items")

    async def list_folders(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        return _array((await self._request("GET", f"{_tcm(ns)}/folders")).json(), "items")

    async def create_folder(self, folder: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_tcm(ns)}/folders", json=folder)).json()

    async def update_folder(self, folder_id: str, fields: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("PATCH", f"{_tcm(ns)}/folders/{quote(folder_id, safe='')}", json=fields)).json()

    async def delete_folder(self, folder_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("DELETE", f"{_tcm(ns)}/folders/{quote(folder_id, safe='')}")

    async def move_folder(self, folder_id: str, to_parent_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("POST", f"{_tcm(ns)}/folders/{quote(folder_id, safe='')}/move", json={"toParentId": to_parent_id})

    # -- attachments --
    async def upload_attachment(self, parent_kind: str, parent_id: str, filename: str, content: bytes,
                                *, media_type: str = "application/octet-stream", namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        url = f"{_tcm(ns)}/attachments/upload"
        try:
            resp = await self._client.request("POST", url, params={"parentKind": parent_kind, "parentId": parent_id},
                                              files={"file": (filename, content, media_type)})
        except Exception as exc:  # noqa: BLE001 — normalised below
            wrap_transport_error(exc)
        raise_for_status(resp)
        return resp.json()

    async def list_attachments(self, parent_kind: str, parent_id: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request("GET", f"{_tcm(ns)}/attachments", params={"parentKind": parent_kind, "parentId": parent_id})
        return _array(resp.json(), "items", "attachments")

    async def download_attachment(self, attachment_id: str, *, namespace: Optional[str] = None) -> bytes:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_tcm(ns)}/attachments/{quote(attachment_id, safe='')}/raw")).content

    async def delete_attachment(self, attachment_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("DELETE", f"{_tcm(ns)}/attachments/{quote(attachment_id, safe='')}")
