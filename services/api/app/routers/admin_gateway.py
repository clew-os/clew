# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Tier-1 admin: gateway routes and upstreams, plugin names only (sysadmin only)."""

from app.core.authorization import admin_router
from app.core.errors import AppError, InfraError
from app.core.reason_codes import ReasonCode
from app.schemas.admin import GatewayOverviewOut
from app.services.admin_gateway import gateway_overview

router = admin_router(prefix="/api/v1/admin", tags=["admin"])


@router.get("/gateway", response_model=GatewayOverviewOut)
def gateway():
    try:
        return gateway_overview()
    except InfraError as exc:
        raise AppError(503, ReasonCode.SERVICE_UNAVAILABLE, "Gateway control API unavailable") from exc
