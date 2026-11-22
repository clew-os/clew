# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Recall notices on committed data: handler re-runs, reconciler repair, per-point content.

The lock goes through the gateway; the running worker creates the notices. Handler and
reconciler are then called directly against the same database.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.business_time import utcnow
from app.models.incident import RecallNotice
from app.worker import incident_handlers
from app.worker.handler_registry import OutboxMessage
from app.worker.incident_handlers import create_recall_notices, reconcile_missing_notices
from tests.integration.conftest import owner_execute
from tests.integration.recall_scene import (
    confirm_suspects,
    incident_detail,
    open_incident,
    recall_scene,
    wait_for,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def locked_incident(session_factory, owner_engine, monkeypatch):
    """Incident with a lock on a private scene and all notices created by the worker."""
    # The handlers open their own sessions: point them at the test database role.
    monkeypatch.setattr(incident_handlers, "new_session", session_factory)
    with recall_scene(session_factory, owner_engine, points=3) as scene:
        incident = open_incident("Notice idempotency probe", scene)
        confirm_suspects(incident["id"], scene)
        wait_for(lambda: len(incident_detail(incident["id"])["notices"]) == scene.points, 30, "worker makes notices")
        yield uuid.UUID(incident["id"]), scene


def _notices(session_factory, incident_id) -> dict:
    with session_factory() as session:
        rows = session.scalars(select(RecallNotice).where(RecallNotice.incident_id == incident_id)).all()
        return {n.delivery_point_id: n for n in rows}


def test_running_the_notice_handler_twice_keeps_one_notice_per_point_and_the_acks(session_factory, locked_incident):
    incident_id, scene = locked_incident
    before = _notices(session_factory, incident_id)
    assert set(before) == set(scene.codes_by_point)
    acked = next(iter(before.values()))
    with session_factory() as session, session.begin():
        row = session.get(RecallNotice, acked.id)
        row.acknowledged_at, row.acknowledged_by = utcnow(), "school-admin"
    message = OutboxMessage(
        0,
        "lock.applied",
        "incident",
        incident_id,
        {"incident_id": str(incident_id), "audit_seq": 1, "audit_hash": "a" * 64},
        1,
    )

    create_recall_notices(message)
    create_recall_notices(message)  # at-least-once delivery: a second run is harmless

    after = _notices(session_factory, incident_id)
    assert {p: n.id for p, n in after.items()} == {p: n.id for p, n in before.items()}  # no duplicate, no new row
    assert after[acked.delivery_point_id].acknowledged_by == "school-admin"
    assert all(after[p].audit_seq == before[p].audit_seq for p in after)  # unchanged content: anchor untouched
    with session_factory() as session:
        count = session.scalar(
            select(func.count()).select_from(RecallNotice).where(RecallNotice.incident_id == incident_id)
        )
    assert count == scene.points


def test_each_notice_lists_only_its_own_delivery_points_shipments(session_factory, locked_incident):
    incident_id, scene = locked_incident
    notices = _notices(session_factory, incident_id)
    for point_id, codes in scene.codes_by_point.items():
        content = notices[point_id].content
        assert {s["shipment"] for s in content["shipments"]} == codes
        assert {s["action"] for s in content["shipments"]} == {"hold", "recall"}
        assert content["delivery_point"].startswith("Point ")
        assert "title" in content and "Notice idempotency probe" not in str(content)  # QA's title never leaks


def test_reconciler_recreates_a_deleted_notice(session_factory, owner_engine, locked_incident):
    incident_id, scene = locked_incident
    victim = next(iter(_notices(session_factory, incident_id).values()))
    owner_execute(owner_engine, "DELETE FROM recall_notice WHERE id = :id", id=victim.id)

    reconcile_missing_notices()  # the worker's own 30 s reconciler may win the race: same outcome

    restored = _notices(session_factory, incident_id)
    assert set(restored) == set(scene.codes_by_point)
    assert {s["shipment"] for s in restored[victim.delivery_point_id].content["shipments"]} == scene.codes_by_point[
        victim.delivery_point_id
    ]
