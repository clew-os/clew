# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Tier-1 admin: health of every core component (sysadmin only)."""

from fastapi import Depends

from app.core.authorization import admin_router
from app.core.settings import Settings, get_settings
from app.schemas.admin import CoreComponentOut
from app.services.admin_core_status import SingleFlightCache, run_probes
from app.services.admin_probes import build_probes

router = admin_router(prefix="/api/v1/admin", tags=["admin"])
_cache = SingleFlightCache(ttl_s=5)


@router.get("/core-status", response_model=list[CoreComponentOut])
def core_status(settings: Settings = Depends(get_settings)):
    # Overall deadline a little above the per-request timeout: probes run in parallel.
    return _cache.get(lambda: run_probes(build_probes(settings), deadline_s=settings.admin_probe_timeout_s + 1))
