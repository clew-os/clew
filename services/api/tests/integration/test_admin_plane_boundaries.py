# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Admin plane boundaries (tier 1), checked against the running stack:

- the public listener (9080) never serves the Keycloak admin console or admin REST;
- the admin listener (9081) serves only realm `clew`'s console, never the master realm,
  the API or the web app;
- app tokens (clew-web, clew-cli) carry app roles only, never Keycloak admin roles,
  so a stolen SPA token is not a Keycloak admin credential;
- the sysadmin can manage users in the console but cannot impersonate anyone.
"""

import os

import httpx
import pytest

from tests.integration.gateway_tokens import GATEWAY, user_token

pytestmark = pytest.mark.integration

ADMIN_PLANE = os.environ.get("ADMIN_PLANE_URL", "http://localhost:9081")
ADMIN_REST = f"{ADMIN_PLANE}/auth/admin/realms/clew"
APP_ROLES = {"qa", "procurement", "chef", "driver", "cskh", "director", "approver", "customer_staff", "sysadmin"}


@pytest.mark.parametrize("path", ["/auth/admin/clew/console/", "/auth/admin/realms/clew", "/auth/admin/serverinfo"])
def test_public_listener_hides_admin_console(path):
    assert httpx.get(f"{GATEWAY}{path}").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/auth/realms/master",
        "/auth/admin/master/console/",
        "/auth/realms/clew/.well-known/openid-configuration",
        "/api/v1/whoami",
        "/",
    ],
)
def test_admin_listener_serves_only_the_clew_console(path):
    assert httpx.get(f"{ADMIN_PLANE}{path}").status_code == 404
    assert httpx.get(f"{ADMIN_PLANE}/auth/admin/clew/console/").status_code == 200


def _admin_headers() -> dict[str, str]:
    # clew-test (CI overlay) keeps full scope, so this token carries the sysadmin's console grants.
    return {"Authorization": f"Bearer {user_token('sysadmin-khoa', scope='openid')}"}


def _user_ids(headers: dict[str, str]) -> dict[str, str]:
    users = httpx.get(f"{ADMIN_REST}/users", headers=headers, params={"max": 100}).json()
    return {u["username"]: u["id"] for u in users}


@pytest.mark.parametrize("client_id", ["clew-web", "clew-cli"])
def test_app_tokens_never_carry_keycloak_admin_roles(client_id):
    headers = _admin_headers()
    ids = _user_ids(headers)
    [client] = httpx.get(f"{ADMIN_REST}/clients", headers=headers, params={"clientId": client_id}).json()
    for username in ("sysadmin-khoa", "qa-lan", "truong-a"):
        res = httpx.get(
            f"{ADMIN_REST}/clients/{client['id']}/evaluate-scopes/generate-example-access-token",
            headers=headers,
            params={"scope": "openid", "userId": ids[username]},
        )
        assert res.status_code == 200
        token = res.json()
        assert not token.get("resource_access"), (client_id, username, token.get("resource_access"))
        assert set(token.get("realm_access", {}).get("roles", [])) <= APP_ROLES


def test_sysadmin_manages_users_but_cannot_impersonate():
    headers = _admin_headers()
    ids = _user_ids(headers)
    assert "qa-lan" in ids
    assert httpx.post(f"{ADMIN_REST}/users/{ids['qa-lan']}/impersonation", headers=headers).status_code == 403


def test_business_user_has_no_admin_rest_access():
    headers = {"Authorization": f"Bearer {user_token('qa-lan', scope='openid')}"}
    assert httpx.get(f"{ADMIN_REST}/users", headers=headers).status_code == 403
