# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Tier-1 admin: workflow engine overview and dead-letter retry (sysadmin only)."""

from typing import Annotated

from fastapi import Path, Response

from app.core.authentication import CurrentPrincipal
from app.core.authorization import admin_router
from app.core.database import DbSession
from app.schemas.admin import WorkflowOverviewOut
from app.services.admin_workflow import retry_deadletter_job, workflow_overview

router = admin_router(prefix="/api/v1/admin", tags=["admin"])

# Flowable job ids are UUIDs; the pattern also keeps the id safe to place in a URL path.
JobId = Annotated[str, Path(min_length=1, max_length=64, pattern="^[A-Za-z0-9-]+$")]


@router.get("/workflow", response_model=WorkflowOverviewOut)
def workflow():
    return workflow_overview()


@router.post("/workflow/deadletter-jobs/{job_id}/retry", status_code=204)
def retry_job(job_id: JobId, session: DbSession, principal: CurrentPrincipal) -> Response:
    retry_deadletter_job(session, job_id, principal.username)
    return Response(status_code=204)
