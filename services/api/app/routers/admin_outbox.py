# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Tier-1 admin: outbox counts, failed events and manual retry (sysadmin only)."""

from fastapi import Path, Response

from app.core.authentication import CurrentPrincipal
from app.core.authorization import admin_router
from app.core.database import DbSession
from app.schemas.admin import OutboxOverviewOut
from app.services.admin_outbox import outbox_overview, retry_failed_event

router = admin_router(prefix="/api/v1/admin", tags=["admin"])


@router.get("/outbox", response_model=OutboxOverviewOut)
def outbox(session: DbSession):
    return outbox_overview(session)


@router.post("/outbox/{event_id}/retry", status_code=204)
def retry_event(session: DbSession, principal: CurrentPrincipal, event_id: int = Path(ge=1, le=2**63 - 1)) -> Response:
    retry_failed_event(session, event_id, principal.username)
    return Response(status_code=204)
