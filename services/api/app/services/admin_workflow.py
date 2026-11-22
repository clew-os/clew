# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Sysadmin view of the workflow engine (Flowable): definitions, tasks, timers, dead-letter jobs."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from sqlalchemy.orm import Session

from app.core.audit_hash_chain import append_audit
from app.core.error_text import sanitize_error_text
from app.core.errors import AppError, not_found
from app.core.reason_codes import ReasonCode
from app.core.settings import get_settings
from app.schemas.admin import (
    DeadLetterJobOut,
    OpenTaskOut,
    ProcessDefinitionOut,
    TimerJobOut,
    WorkflowOverviewOut,
)
from app.workflow.flowable_client import (
    FlowableClient,
    FlowableError,
    FlowableNotFoundError,
    FlowableUnavailableError,
)

ERROR_MAX_CHARS = 300
OVERVIEW_DEADLINE_S = 6.0  # whole overview, not per request: a dead engine must not cost N x timeout


def admin_flowable_client() -> FlowableClient:
    settings = get_settings()
    return FlowableClient(
        settings.flowable_url,
        settings.flowable_user,
        settings.flowable_password,
        timeout=settings.admin_probe_timeout_s,
    )


def _unavailable() -> AppError:
    return AppError(503, ReasonCode.SERVICE_UNAVAILABLE, "Workflow engine unavailable")


def _text(value: Any, limit: int | None = None) -> str | None:
    if value is None:
        return None
    return str(value)[:limit] if limit else str(value)


def _collect() -> tuple[list[ProcessDefinitionOut], list, list, list]:
    with admin_flowable_client() as flowable:
        definitions = [
            ProcessDefinitionOut(
                key=d["key"],
                name=d.get("name"),
                version=int(d["version"]),
                deployment_id=d.get("deploymentId"),
                running_instances=flowable.running_instance_count(d["key"]),
            )
            for d in flowable.latest_process_definitions()
        ]
        return definitions, flowable.open_tasks(), flowable.timer_jobs(), flowable.deadletter_jobs()


def workflow_overview() -> WorkflowOverviewOut:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="admin-workflow")
    try:
        definitions, tasks, timers, dead = executor.submit(_collect).result(timeout=OVERVIEW_DEADLINE_S)
    except (FlowableUnavailableError, FlowableError, FutureTimeout) as exc:
        raise _unavailable() from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return WorkflowOverviewOut(
        definitions=sorted(definitions, key=lambda d: d.key),
        open_tasks=[
            OpenTaskOut(
                id=t["id"],
                name=t.get("name"),
                process_instance_id=t.get("processInstanceId"),
                assignee=t.get("assignee"),
                created=_text(t.get("createTime")),
            )
            for t in tasks
        ],
        timer_jobs=[
            TimerJobOut(
                id=j["id"],
                process_instance_id=j.get("processInstanceId"),
                due_date=_text(j.get("dueDate")),
                retries=j.get("retries"),
            )
            for j in timers
        ],
        deadletter_jobs=[
            DeadLetterJobOut(
                id=j["id"],
                process_instance_id=j.get("processInstanceId"),
                exception_message=sanitize_error_text(j.get("exceptionMessage") or "", ERROR_MAX_CHARS) or None,
                retries=j.get("retries"),
                created=_text(j.get("createTime")),
            )
            for j in dead
        ],
    )


def retry_deadletter_job(session: Session, job_id: str, actor: str) -> None:
    """Audit row first (same transaction), then Flowable; commit only if Flowable accepted it."""
    try:
        append_audit(
            session,
            actor=actor,
            action="admin.workflow.deadletter_retry",
            entity_type="flowable_job",
            entity_id=job_id,
        )
        with admin_flowable_client() as flowable:
            flowable.retry_deadletter_job(job_id)
        session.commit()
    except FlowableNotFoundError as exc:
        session.rollback()
        raise not_found("Dead-letter job") from exc
    except (FlowableUnavailableError, FlowableError) as exc:
        session.rollback()
        raise _unavailable() from exc
    except Exception:
        session.rollback()
        raise
