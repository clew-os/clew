# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Response shapes of the sysadmin endpoints (/api/v1/admin). Generic: no business concepts."""

from typing import Any, Literal

from pydantic import BaseModel

ComponentStatus = Literal["up", "degraded", "down"]
ServiceKind = Literal["sso", "gateway", "structured_data", "unstructured_data", "workflow", "platform"]


class CoreComponentOut(BaseModel):
    key: str
    label: str
    service_kind: ServiceKind
    status: ComponentStatus
    latency_ms: int
    facts: dict[str, Any]
    console_url: str | None
    # Second native console of the same component (SeaweedFS filer); null for the others.
    secondary_console_url: str | None = None


class ProcessDefinitionOut(BaseModel):
    key: str
    name: str | None
    version: int
    deployment_id: str | None
    running_instances: int


class OpenTaskOut(BaseModel):
    id: str
    name: str | None
    process_instance_id: str | None
    assignee: str | None
    created: str | None


class TimerJobOut(BaseModel):
    id: str
    process_instance_id: str | None
    due_date: str | None
    retries: int | None


class DeadLetterJobOut(BaseModel):
    id: str
    process_instance_id: str | None
    exception_message: str | None
    retries: int | None
    created: str | None


class WorkflowOverviewOut(BaseModel):
    definitions: list[ProcessDefinitionOut]
    open_tasks: list[OpenTaskOut]
    timer_jobs: list[TimerJobOut]
    deadletter_jobs: list[DeadLetterJobOut]


class FailedOutboxEventOut(BaseModel):
    id: int
    event_type: str
    attempts: int
    failed_at: str | None
    last_error: str | None


class OutboxOverviewOut(BaseModel):
    pending: int
    processed: int
    failed: int
    oldest_pending_age_s: int | None
    last_processed_at: str | None
    failed_events: list[FailedOutboxEventOut]


class GatewayRouteOut(BaseModel):
    id: str
    uris: list[str]
    priority: int
    upstream_id: str | None
    # Plugin NAMES only: plugin configuration can hold secrets and is never returned.
    plugins: list[str]


class GatewayUpstreamOut(BaseModel):
    id: str
    nodes: list[str]


class GatewayOverviewOut(BaseModel):
    routes: list[GatewayRouteOut]
    upstreams: list[GatewayUpstreamOut]
