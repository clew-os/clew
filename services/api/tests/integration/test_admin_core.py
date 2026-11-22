# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Tier-1 admin API through the gateway, with the real stack behind it."""

import secrets

import httpx
import pytest

from tests.integration.gateway_tokens import GATEWAY, auth, user_token

pytestmark = pytest.mark.integration

COMPONENT_KEYS = {"postgres", "keycloak", "apisix", "seaweedfs", "flowable", "outbox", "audit"}
MUST_BE_UP = {"postgres", "keycloak", "apisix", "seaweedfs", "flowable"}


def _get(path: str, user: str = "sysadmin-khoa") -> httpx.Response:
    return httpx.get(f"{GATEWAY}{path}", headers=auth(user_token(user)), timeout=20)


def test_core_status_lists_every_component_and_the_core_is_up():
    res = _get("/api/v1/admin/core-status")
    assert res.status_code == 200, res.text
    components = {c["key"]: c for c in res.json()}
    assert set(components) >= COMPONENT_KEYS
    for key in MUST_BE_UP:
        assert components[key]["status"] == "up", components[key]
    assert components["keycloak"]["console_url"].endswith("/admin/clew/console/")
    assert components["seaweedfs"]["secondary_console_url"]
    assert components["flowable"]["facts"]["version"]
    assert "hunter" not in res.text and "secret" not in res.text.lower()


def test_workflow_overview_lists_deployed_definitions():
    res = _get("/api/v1/admin/workflow")
    assert res.status_code == 200, res.text
    body = res.json()
    assert {"incident-recall", "cold-chain-alert"} <= {d["key"] for d in body["definitions"]}
    assert all(isinstance(d["running_instances"], int) for d in body["definitions"])
    assert isinstance(body["deadletter_jobs"], list)


def test_outbox_overview_has_counts():
    res = _get("/api/v1/admin/outbox")
    assert res.status_code == 200, res.text
    body = res.json()
    assert {"pending", "processed", "failed", "failed_events"} <= set(body)


def test_gateway_overview_never_contains_secrets():
    res = _get("/api/v1/admin/gateway")
    assert res.status_code == 200, res.text
    assert "secret" not in res.text.lower()
    body = res.json()
    assert any(r["id"] == "api" and "openid-connect" in r["plugins"] for r in body["routes"])
    assert any(u["id"] == "api" for u in body["upstreams"])


def test_unknown_outbox_event_and_job_are_404():
    missing = httpx.post(
        f"{GATEWAY}/api/v1/admin/outbox/{secrets.randbelow(10**9) + 10**12}/retry",
        headers=auth(user_token("sysadmin-khoa")),
        timeout=20,
    )
    assert missing.status_code == 404
    job = httpx.post(
        f"{GATEWAY}/api/v1/admin/workflow/deadletter-jobs/{secrets.token_hex(8)}/retry",
        headers=auth(user_token("sysadmin-khoa")),
        timeout=20,
    )
    assert job.status_code == 404


def test_business_staff_cannot_use_admin_and_sysadmin_cannot_read_business_data():
    assert _get("/api/v1/admin/core-status", "qa-lan").status_code == 403
    assert _get("/api/v1/admin/outbox", "director-nam").status_code == 403
    assert _get("/api/v1/lots", "sysadmin-khoa").status_code == 403
