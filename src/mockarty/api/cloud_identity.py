# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Cloud account sign-in methods and step-up verification."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class CloudIdentityAPI(SyncAPIBase):
    def request_email_change(self, new_email: str, *, current_password: str = "", totp_code: str = "") -> dict[str, Any]:
        if not new_email:
            raise ValueError("new_email is required")
        return self._request("PATCH", "/api/v1/cloud/email", json={
            "new_email": new_email, "current_password": current_password, "totp_code": totp_code,
        }).json()

    def authorize_current_email(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValueError("token is required")
        return self._request("POST", "/api/v1/cloud/auth/email/change/authorize", json={"token": token}).json()

    def confirm_new_email(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValueError("token is required")
        return self._request("POST", "/api/v1/cloud/auth/email/change/confirm", json={"token": token}).json()

    def cancel_email_change(self) -> None:
        self._request("DELETE", "/api/v1/cloud/email/pending")

    def list(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/cloud/auth/oauth/identities").json()
        return data.get("identities", []) if isinstance(data, dict) else []

    def step_up(self, action: str, *, credential: str = "", force_credential: bool = False) -> dict[str, Any]:
        if not action:
            raise ValueError("action is required")
        return self._request("POST", "/api/v1/cloud/auth/step-up", json={
            "action": action, "credential": credential, "force_credential": force_credential,
        }).json()

    def unlink(self, provider: str, *, idempotency_key: str) -> None:
        if not provider or not idempotency_key:
            raise ValueError("provider and idempotency_key are required")
        self._request("DELETE", f"/api/v1/cloud/auth/oauth/identities/{quote(provider, safe='')}",
                      headers={"Idempotency-Key": idempotency_key})

    def link_url(self, provider: str) -> str:
        if not provider:
            raise ValueError("provider is required")
        return str(self._client.base_url.join(f"/api/v1/cloud/auth/oauth/{quote(provider, safe='')}/link"))


class AsyncCloudIdentityAPI(AsyncAPIBase):
    async def request_email_change(self, new_email: str, *, current_password: str = "", totp_code: str = "") -> dict[str, Any]:
        if not new_email:
            raise ValueError("new_email is required")
        return (await self._request("PATCH", "/api/v1/cloud/email", json={
            "new_email": new_email, "current_password": current_password, "totp_code": totp_code,
        })).json()

    async def authorize_current_email(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValueError("token is required")
        return (await self._request("POST", "/api/v1/cloud/auth/email/change/authorize", json={"token": token})).json()

    async def confirm_new_email(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValueError("token is required")
        return (await self._request("POST", "/api/v1/cloud/auth/email/change/confirm", json={"token": token})).json()

    async def cancel_email_change(self) -> None:
        await self._request("DELETE", "/api/v1/cloud/email/pending")

    async def list(self) -> list[dict[str, Any]]:
        data = (await self._request("GET", "/api/v1/cloud/auth/oauth/identities")).json()
        return data.get("identities", []) if isinstance(data, dict) else []

    async def step_up(self, action: str, *, credential: str = "", force_credential: bool = False) -> dict[str, Any]:
        if not action:
            raise ValueError("action is required")
        return (await self._request("POST", "/api/v1/cloud/auth/step-up", json={
            "action": action, "credential": credential, "force_credential": force_credential,
        })).json()

    async def unlink(self, provider: str, *, idempotency_key: str) -> None:
        if not provider or not idempotency_key:
            raise ValueError("provider and idempotency_key are required")
        await self._request("DELETE", f"/api/v1/cloud/auth/oauth/identities/{quote(provider, safe='')}",
                            headers={"Idempotency-Key": idempotency_key})

    def link_url(self, provider: str) -> str:
        if not provider:
            raise ValueError("provider is required")
        return str(self._client.base_url.join(f"/api/v1/cloud/auth/oauth/{quote(provider, safe='')}/link"))
