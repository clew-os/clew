# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""A private recall scene committed to the dev database, plus gateway helpers.

One batch feeds N delivery points. Each point gets two shipments of its own: a planned one
(the lock holds it) and a dispatched one (the notice recalls it). Nothing links the scene to
demo data, so a lock on its batch can never touch anything else. `recall_scene` deletes its
rows again (as schema owner), so global lists such as "today's shipments" keep their size.
"""

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from app.core.business_time import service_date
from app.models.cooking import CookingBatch, Dish
from app.models.enums import ShipmentStatus
from app.models.kitchen_and_customers import CustomerOrg, DeliveryPoint, Kitchen
from app.models.shipment import Shipment, ShipmentItem
from tests.integration.gateway_tokens import GATEWAY, auth, user_token


@dataclass
class Scene:
    kitchen_id: uuid.UUID
    org_id: uuid.UUID
    dish_id: uuid.UUID
    batch_id: uuid.UUID
    held: list[uuid.UUID] = field(default_factory=list)  # planned today: the lock must hold them
    dispatched: list[uuid.UUID] = field(default_factory=list)  # already out: recall notice
    codes_by_point: dict[uuid.UUID, set[str]] = field(default_factory=dict)
    incident_ids: list[str] = field(default_factory=list)  # opened through open_incident(), closed on exit

    @property
    def points(self) -> int:
        return len(self.codes_by_point)


def build_recall_scene(session_factory, points: int = 4) -> Scene:
    tag = uuid.uuid4().hex[:8].upper()
    today = service_date()  # business calendar, like the rest of the suite
    with session_factory() as session:

        def add(row):
            session.add(row)
            session.flush()
            return row

        kitchen = add(Kitchen(code=f"K-{tag}", name="Recall scene kitchen"))
        org = add(CustomerOrg(kc_org_alias=f"org-{tag}", name="Recall scene org", kind="school", profile={}))
        dish = add(Dish(code=f"D-{tag}", name="Recall scene dish", kind="solid"))
        batch = add(
            CookingBatch(
                kitchen_id=kitchen.id,
                dish_id=dish.id,
                batch_code=f"B-{tag}",
                service_date=today,
                meal_slot="lunch",
                owner="t",
            )
        )
        scene = Scene(kitchen_id=kitchen.id, org_id=org.id, dish_id=dish.id, batch_id=batch.id)
        for n in range(points):
            point = add(DeliveryPoint(customer_org_id=org.id, code=f"DP{n}-{tag}", name=f"Point {n} {tag}"))
            scene.codes_by_point[point.id] = set()
            for kind, status in (("P", ShipmentStatus.PLANNED), ("D", ShipmentStatus.DISPATCHED)):
                shipment = Shipment(
                    kitchen_id=kitchen.id,
                    code=f"{kind}{n}-{tag}",
                    delivery_point_id=point.id,
                    service_date=today,
                    meal_slot="lunch",
                    status=status,
                    dispatched_at=datetime.now(UTC) if status == ShipmentStatus.DISPATCHED else None,
                )
                add(shipment)
                add(ShipmentItem(shipment_id=shipment.id, batch_id=batch.id, portions=10))
                scene.codes_by_point[point.id].add(shipment.code)
                (scene.held if status == ShipmentStatus.PLANNED else scene.dispatched).append(shipment.id)
        session.commit()
    return scene


@contextmanager
def recall_scene(session_factory, owner_engine, points: int = 4):
    scene = build_recall_scene(session_factory, points)
    try:
        yield scene
    finally:  # runs when an assert fails too: no open incident with locks on deleted rows stays behind
        for incident_id in scene.incident_ids:
            _force_close(owner_engine, incident_id)
        drop_recall_scene(owner_engine, scene)


def _force_close(owner_engine, incident_id: str) -> None:
    """Four-eyes close through the API; if that fails (stack hurt, assert mid-flow), close it in SQL."""
    try:
        if incident_detail(incident_id)["status"] != "closed":
            close_incident(incident_id)
        return
    except Exception as exc:
        print(f"cleanup: API close of incident {incident_id} failed ({exc!r}), closing in SQL")
    with owner_engine.begin() as conn:
        conn.execute(
            text("UPDATE lock SET active = false, released_at = now() WHERE incident_id = :i AND active"),
            {"i": incident_id},
        )
        conn.execute(
            text("UPDATE incident SET status = 'closed', closed_at = now() WHERE id = :i AND status <> 'closed'"),
            {"i": incident_id},
        )


def drop_recall_scene(owner_engine, scene: Scene) -> None:
    shipments, points = [*scene.held, *scene.dispatched], list(scene.codes_by_point)
    with owner_engine.begin() as conn:
        for sql in (
            "DELETE FROM recall_notice WHERE delivery_point_id = ANY(:points)",
            "DELETE FROM shipment_item WHERE shipment_id = ANY(:shipments)",
            "DELETE FROM shipment WHERE id = ANY(:shipments)",
            "DELETE FROM cooking_batch WHERE id = :batch",
            "DELETE FROM delivery_point WHERE id = ANY(:points)",
            "DELETE FROM dish WHERE id = :dish",
            "DELETE FROM customer_org WHERE id = :org",
            "DELETE FROM kitchen WHERE id = :kitchen",
        ):
            conn.execute(
                text(sql),
                {
                    "points": points,
                    "shipments": shipments,
                    "batch": scene.batch_id,
                    "dish": scene.dish_id,
                    "org": scene.org_id,
                    "kitchen": scene.kitchen_id,
                },
            )


def call(method: str, path: str, user: str, **kwargs) -> httpx.Response:
    return httpx.request(method, f"{GATEWAY}/api/v1{path}", headers=auth(user_token(user)), timeout=30, **kwargs)


def ok(res: httpx.Response, status: int = 200):
    assert res.status_code == status, res.text
    return res.json()


def wait_for(predicate, seconds: float, what: str, interval: float = 1.0):
    """Poll until `predicate()` is truthy and return its value; fail with `what` after `seconds`."""
    deadline = time.monotonic() + seconds
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            pytest.fail(f"not met within {seconds:.0f}s: {what}")
        time.sleep(interval)


def open_incident(title: str, scene: Scene) -> dict:
    incident = ok(call("POST", "/incidents", "qa-lan", json={"title": title}), 201)
    scene.incident_ids.append(incident["id"])
    return incident


def confirm_suspects(incident_id: str, scene: Scene) -> dict:
    body = {"nodes": [{"type": "batch", "id": str(scene.batch_id)}], "lock_lots": False}
    return ok(call("POST", f"/incidents/{incident_id}/confirm-suspects", "qa-lan", json=body))


def incident_detail(incident_id: str) -> dict:
    return ok(call("GET", f"/incidents/{incident_id}", "qa-lan"))


def close_incident(incident_id: str) -> None:
    """Four-eyes close: releases the locks and ends the Flowable process."""
    request = ok(call("POST", f"/incidents/{incident_id}/close-requests", "qa-lan", json={"note": "test"}), 201)
    assert ok(call("POST", f"/close-requests/{request['id']}/approve", "approver-ha"))["status"] == "closed"
