# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Disposal of held shipments: held food is never released, QA records its destruction."""

import uuid

from sqlalchemy.orm import Session

from app.core.audit_hash_chain import append_audit
from app.core.business_time import utcnow
from app.core.database import get_or_404
from app.core.errors import AppError
from app.core.principal import Principal
from app.core.reason_codes import ReasonCode
from app.models.enums import ShipmentStatus
from app.models.shipment import Shipment


def dispose(session: Session, principal: Principal, shipment_id: uuid.UUID, reason: str) -> Shipment:
    """QA records that held food was destroyed. Terminal: disposed shipments are never released.

    Allowed whether or not the incident that held the shipment is closed: P3 limits hot-holding
    to 120 minutes, so held food is past its limit long before an incident closes.
    """
    shipment = get_or_404(session, Shipment, shipment_id, "shipment", for_update=True)
    if shipment.status != ShipmentStatus.HELD:
        raise AppError(409, ReasonCode.CONFLICT, f"Only a held shipment can be disposed; shipment is {shipment.status}")
    shipment.status = ShipmentStatus.DISPOSED
    shipment.disposed_at = utcnow()
    shipment.disposed_by = principal.username
    shipment.disposal_reason = reason
    append_audit(
        session,
        actor=principal.username,
        action="shipment.disposed",
        entity_type="shipment",
        entity_id=shipment.id,
        payload={"code": shipment.code, "reason": reason},
    )
    session.commit()
    return shipment
