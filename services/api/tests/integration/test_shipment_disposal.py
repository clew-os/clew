# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Held food is never released: QA records its disposal (through the gateway).

Each test creates its own empty shipment far in the future, forces it into `held`
with the owner role (the lock path that normally does this is covered elsewhere),
and deletes it afterwards; the audit rows stay (the chain is append-only).
"""

import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.business_time import service_date
from app.models.platform import AuditEvent
from tests.integration.conftest import owner_execute
from tests.integration.gateway_tokens import GATEWAY, auth, user_token

pytestmark = pytest.mark.integration


def call(method: str, path: str, user: str, **kwargs) -> httpx.Response:
    return httpx.request(method, f"{GATEWAY}/api/v1{path}", headers=auth(user_token(user)), timeout=30, **kwargs)


def ok(res: httpx.Response, status: int = 200):
    assert res.status_code == status, res.text
    return res.json()


@pytest.fixture
def make_shipment(owner_engine):
    created: list[str] = []
    points = ok(call("GET", "/delivery-points", "cskh-thu"))

    def make(status: str = "held") -> dict:
        day = service_date() + timedelta(days=400 + len(created))
        body = {"delivery_point_id": points[0]["id"], "service_date": str(day), "meal_slot": "dinner"}
        shipment = ok(call("POST", "/shipments", "chef-hung", json=body), 201)
        created.append(shipment["id"])
        # A `disposed` row must carry its record (CHECK ck_shipment_disposed_has_record).
        owner_execute(
            owner_engine,
            "UPDATE shipment SET status = CAST(:s AS varchar),"
            " disposed_at = CASE WHEN CAST(:s AS varchar) = 'disposed' THEN now() END,"
            " disposed_by = CASE WHEN CAST(:s AS varchar) = 'disposed' THEN 'seed' END,"
            " disposal_reason = CASE WHEN CAST(:s AS varchar) = 'disposed' THEN 'seed' END WHERE id = :id",
            s=status,
            id=shipment["id"],
        )
        return shipment

    yield make
    for shipment_id in created:
        owner_execute(owner_engine, "DELETE FROM shipment WHERE id = :id", id=shipment_id)


def mine(shipment: dict) -> dict:
    """Our shipment from the day list, found by id (never by position)."""
    listed = ok(call("GET", f"/shipments?day={shipment['service_date']}", "qa-lan"))
    return next(s for s in listed if s["id"] == shipment["id"])


def test_qa_disposes_a_held_shipment_and_it_is_audited(make_shipment, app_session):
    shipment = make_shipment()
    disposed = ok(call("POST", f"/shipments/{shipment['id']}/dispose", "qa-lan", json={"reason": "  Quá 120 phút  "}))
    assert disposed["status"] == "disposed"
    assert disposed["disposal_reason"] == "Quá 120 phút"
    assert disposed["disposed_by"] == "qa-lan"
    assert disposed["disposed_at"]
    assert [b["code"] for b in disposed["blockers"]][:1] == ["P3_SHIPMENT_DISPOSED"]  # never "ready to go"
    event = app_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "shipment.disposed", AuditEvent.entity_id == shipment["id"])
    ).one()
    assert event.actor == "qa-lan"
    assert event.payload["reason"] == "Quá 120 phút"
    assert mine(shipment)["status"] == "disposed"


@pytest.mark.parametrize("status", ["planned", "ready", "dispatched", "delivered", "disposed"])
def test_only_a_held_shipment_can_be_disposed(make_shipment, status):
    shipment = make_shipment(status)
    res = call("POST", f"/shipments/{shipment['id']}/dispose", "qa-lan", json={"reason": "x"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


# Not approver-ha: that account is also QA, so it may dispose.
@pytest.mark.parametrize("user", ["chef-hung", "driver-tuan", "director-nam", "cskh-thu"])
def test_only_qa_may_dispose(make_shipment, user):
    shipment = make_shipment()
    assert call("POST", f"/shipments/{shipment['id']}/dispose", user, json={"reason": "x"}).status_code == 403
    assert mine(shipment)["status"] == "held"


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "   "}, {"reason": "x" * 501}])
def test_reason_is_required_and_bounded(make_shipment, body):
    shipment = make_shipment()
    assert call("POST", f"/shipments/{shipment['id']}/dispose", "qa-lan", json=body).status_code == 422


def test_approver_who_is_also_qa_may_dispose(make_shipment):
    shipment = make_shipment()
    res = ok(call("POST", f"/shipments/{shipment['id']}/dispose", "approver-ha", json={"reason": "x"}))
    assert res["disposed_by"] == "approver-ha"


def test_portion_check_on_a_disposed_shipment_is_refused(make_shipment):
    shipment = make_shipment("disposed")
    body = {"batch_id": str(uuid.uuid4()), "shipment_id": shipment["id"], "portions": 1}
    res = call("POST", "/portion-checks", "qa-lan", json=body)
    assert res.status_code == 422
    assert "P3_SHIPMENT_DISPOSED" in {v["code"] for v in res.json()["error"]["details"]["violations"]}


def test_disposed_shipment_can_never_be_dispatched(make_shipment):
    shipment = make_shipment()
    ok(call("POST", f"/shipments/{shipment['id']}/dispose", "qa-lan", json={"reason": "Hủy"}))
    res = call("POST", f"/shipments/{shipment['id']}/dispatch", "driver-tuan")
    assert res.status_code == 422
    assert "P3_SHIPMENT_DISPOSED" in {v["code"] for v in res.json()["error"]["details"]["violations"]}
    assert call("POST", f"/shipments/{shipment['id']}/dispose", "qa-lan", json={"reason": "Lại"}).status_code == 409


def test_closing_an_unrelated_incident_leaves_held_food_held_and_disposal_still_works(make_shipment):
    shipment = make_shipment()
    incident = ok(call("POST", "/incidents", "qa-lan", json={"title": "Disposal probe"}), 201)
    request = ok(call("POST", f"/incidents/{incident['id']}/close-requests", "qa-lan", json={}), 201)
    assert ok(call("POST", f"/close-requests/{request['id']}/approve", "approver-ha"))["status"] == "closed"

    # The incident never locked this shipment (status set by SQL): closing an incident touches no shipment.
    assert mine(shipment)["status"] == "held"
    assert "P3_SHIPMENT_HELD" in {
        v["code"]
        for v in call("POST", f"/shipments/{shipment['id']}/dispatch", "chef-hung").json()["error"]["details"][
            "violations"
        ]
    }

    disposed = ok(call("POST", f"/shipments/{shipment['id']}/dispose", "qa-lan", json={"reason": "Sự cố đã đóng"}))
    assert disposed["status"] == "disposed"
    assert uuid.UUID(disposed["id"]) == uuid.UUID(shipment["id"])
