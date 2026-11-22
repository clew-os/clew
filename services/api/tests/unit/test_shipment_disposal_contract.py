# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Disposal contract that needs no database: schema, status list, notice action, role gate."""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.authentication import get_principal
from app.core.principal import Principal
from app.main import create_app
from app.models.enums import ShipmentStatus
from app.models.shipment import Shipment
from app.schemas.shipment_schemas import ShipmentDisposeIn
from app.worker.recall_notices import ACTION


def test_reason_is_trimmed_required_and_bounded():
    assert ShipmentDisposeIn(reason="  Quá 120 phút ").reason == "Quá 120 phút"
    for bad in ("", "   ", "x" * 501):
        with pytest.raises(ValidationError):
            ShipmentDisposeIn(reason=bad)


def test_disposed_is_an_allowed_status_in_the_check_constraint():
    sql = [str(c.sqltext) for c in Shipment.__table__.constraints if "sqltext" in vars(c) or hasattr(c, "sqltext")]
    assert any("'disposed'" in s for s in sql)
    assert ShipmentStatus.DISPOSED == "disposed"


def test_disposal_does_not_change_what_the_customer_must_do():
    assert ACTION["disposed"] == ACTION["held"] == "hold"


@pytest.mark.parametrize("role", ["chef", "driver", "approver", "cskh", "procurement", "director"])
def test_only_qa_may_dispose(role):
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal(
        sub="t", username="t", roles=frozenset({role}), org_aliases=frozenset()
    )
    res = TestClient(app).post(f"/api/v1/shipments/{uuid.uuid4()}/dispose", json={"reason": "x"})
    assert res.status_code == 403


def test_reason_is_trimmed_before_the_length_check():
    assert len(ShipmentDisposeIn(reason=" " + "x" * 500).reason) == 500
