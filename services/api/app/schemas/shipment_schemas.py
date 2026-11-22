# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas of shipments and their disposal."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import MealSlot
from app.schemas.findings import Finding


class ShipmentIn(BaseModel):
    delivery_point_id: uuid.UUID
    service_date: date
    meal_slot: MealSlot
    vehicle_asset_id: uuid.UUID | None = None


class ShipmentDisposeIn(BaseModel):
    # Trimmed first, then length-checked: blank is rejected, 500 real characters are accepted.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] = Field(
        description="Why the held food is destroyed (required)"
    )


class ShipmentItemIn(BaseModel):
    batch_id: uuid.UUID
    portions: int = Field(gt=0, le=100000)


class ShipmentItemOut(BaseModel):
    batch_id: uuid.UUID
    batch_code: str
    portions: int
    form3_done: bool


class ShipmentOut(BaseModel):
    id: uuid.UUID
    code: str
    delivery_point_id: uuid.UUID
    delivery_point: str
    service_date: date
    meal_slot: str
    status: str
    dispatched_at: datetime | None
    disposed_at: datetime | None = None
    disposed_by: str | None = None
    disposal_reason: str | None = None
    items: list[ShipmentItemOut]
    blockers: list[Finding] = Field(
        description="What P3 would block right now (empty = ready to go). Disposed: P3_SHIPMENT_DISPOSED."
    )
