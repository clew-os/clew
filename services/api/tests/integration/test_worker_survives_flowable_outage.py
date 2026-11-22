# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Flowable down for 60 s: the API keeps working, the outbox waits, everything catches up.

Stops the real Flowable container (`docker compose stop flowable`, repo root), always starts it
again and waits until healthy. Adds ~2 minutes; select or skip it with `-m outage`.
"""

import subprocess
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.models.platform import OutboxEvent
from tests.integration.gateway_tokens import GATEWAY, auth, user_token
from tests.integration.recall_scene import (
    close_incident,
    confirm_suspects,
    incident_detail,
    open_incident,
    recall_scene,
    wait_for,
)

pytestmark = [pytest.mark.integration, pytest.mark.outage]

REPO_ROOT = Path(__file__).resolve().parents[4]
OUTAGE_SECONDS = 60
FLOWABLE_BOOT_SECONDS = 240


def _compose(*args: str) -> str:
    # Fixed argv, no shell: only service names written in this file.
    done = subprocess.run(  # noqa: S603
        ["docker", "compose", *args],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, f"docker compose {' '.join(args)} failed: {done.stderr[-500:]}"
    return done.stdout.strip()


def _flowable_health() -> str:
    container = _compose("ps", "-q", "flowable")
    if not container:
        return "stopped"
    return _compose("ps", "--format", "{{.Health}}", "flowable") or "unknown"


@pytest.fixture
def flowable_stopped():
    """Flowable is down while the test body runs; it is ALWAYS started again and healthy afterwards."""
    _compose("stop", "flowable")
    stopped_at = time.monotonic()
    try:
        yield stopped_at
    finally:
        _compose("start", "flowable")
        wait_for(lambda: _flowable_health() == "healthy", FLOWABLE_BOOT_SECONDS, "flowable healthy again", 3)


@pytest.fixture
def scene(session_factory, owner_engine):
    with recall_scene(session_factory, owner_engine, points=3) as built:
        yield built


def _component(key: str) -> dict:
    res = httpx.get(f"{GATEWAY}/api/v1/admin/core-status", headers=auth(user_token("sysadmin-khoa")), timeout=30)
    assert res.status_code == 200, res.text
    return next(c for c in res.json() if c["key"] == key)


def _outbox(session_factory, incident_id: str) -> dict[str, OutboxEvent]:
    with session_factory() as session:
        rows = session.scalars(select(OutboxEvent).where(OutboxEvent.payload["incident_id"].astext == incident_id))
        return {e.event_type: e for e in rows}


def _open_tasks(process_instance_id: str) -> list[dict]:
    res = httpx.get(f"{GATEWAY}/api/v1/admin/workflow", headers=auth(user_token("sysadmin-khoa")), timeout=30)
    assert res.status_code == 200, res.text
    return [t for t in res.json()["open_tasks"] if t["process_instance_id"] == process_instance_id]


def test_worker_and_api_survive_a_sixty_second_flowable_outage(session_factory, scene, flowable_stopped):
    wait_for(lambda: _component("flowable")["status"] == "down", 30, "core-status reports flowable down", 2)

    # Business work needs no Flowable: lock, hold and recall notices all commit on the API side.
    incident = open_incident("Flowable outage probe", scene)
    result = confirm_suspects(incident["id"], scene)
    assert result["incident"]["status"] == "contained"
    assert set(map(str, scene.held)) == set(result["held_shipments"])
    detail = wait_for(
        lambda: len((d := incident_detail(incident["id"]))["notices"]) == scene.points and d,
        30,
        "recall notices created while flowable is down",
    )
    assert detail["process_instance_id"] is None
    assert any(s["status"] == "held" for s in detail["shipments"])

    # Events that need Flowable keep retrying with backoff and are never marked failed. Polled, not
    # slept: the attempt timing depends on when the worker picked the events up.
    names = ("incident.opened", "incident.suspects_confirmed")

    def retried_twice():
        events = _outbox(session_factory, incident["id"])
        return len(events) >= len(names) and all(events[n].attempts >= 2 for n in names) and events

    early = wait_for(retried_twice, 40, "both Flowable events retried at least twice", 1)
    for name in names:
        assert early[name].processed_at is None and early[name].failed_at is None, name
    time.sleep(max(0, OUTAGE_SECONDS - 2 - (time.monotonic() - flowable_stopped)))
    late = _outbox(session_factory, incident["id"])
    for name in names:
        assert late[name].processed_at is None and late[name].failed_at is None, name
        assert late[name].attempts > early[name].attempts, name
        assert "/service/" in (late[name].last_error or ""), name  # the failed Flowable REST call
    assert _component("flowable")["status"] == "down"
    time.sleep(max(0, OUTAGE_SECONDS - (time.monotonic() - flowable_stopped)))

    # Flowable returns: the process appears, the outbox drains, core-status recovers.
    _compose("start", "flowable")
    wait_for(lambda: _flowable_health() == "healthy", FLOWABLE_BOOT_SECONDS, "flowable healthy", 3)
    recovered = wait_for(
        lambda: (d := incident_detail(incident["id"]))["process_instance_id"] and d,
        180,
        "incident-recall process exists for the incident",
    )
    # Right after the process exists (whoever started it synced it): triage is already done, so the
    # SLA timer cannot escalate a contained incident, whatever INCIDENT_TRIAGE_SLA is.
    names_open = {t["name"] for t in _open_tasks(recovered["process_instance_id"])}
    assert names_open <= {"Approver: four-eyes close"}, names_open
    wait_for(
        lambda: all(e.processed_at for e in _outbox(session_factory, incident["id"]).values()),
        180,
        "outbox drained for the incident",
    )
    events = _outbox(session_factory, incident["id"])
    assert all(e.failed_at is None for e in events.values())
    wait_for(lambda: _component("flowable")["status"] == "up", 30, "core-status reports flowable up", 2)

    # The process waits at the four-eyes close and never escalated the contained incident.
    assert {t["name"] for t in _open_tasks(recovered["process_instance_id"])} == {"Approver: four-eyes close"}
    assert incident_detail(incident["id"])["escalated"] is False
    close_incident(incident["id"])
    assert incident_detail(incident["id"])["status"] == "closed"
