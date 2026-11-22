# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Outbox handlers + reconcilers for incidents. Only the worker talks to Flowable.

- incident.opened             -> start `incident-recall` (business key incident:<id>, idempotent)
- incident.suspects_confirmed -> complete `qa_triage` if it is still open
- incident.closed             -> complete `close_approval` if it is still open
- lock.applied                -> recall notices per affected delivery point (idempotent)
Whoever starts a process (handler or reconciler) then syncs its tasks with the incident's CURRENT
status (contained -> qa_triage done, closed -> all done): events that arrived while no process
existed (Flowable outage) lose nothing, so they may return quietly.
Reconcilers (30 s, skipping incidents whose incident.opened is still pending): start missing
processes, mirror director escalation as a red flag, create notices that a crash may have skipped.
"""

import logging
import uuid

from sqlalchemy import exists, select

from app.core.database import new_session
from app.core.settings import get_settings
from app.models.enums import IncidentStatus
from app.models.incident import Incident
from app.models.platform import OutboxEvent
from app.worker.handler_registry import OutboxMessage, handles, reconciler
from app.worker.recall_notices import points_missing_notice, upsert_notices
from app.workflow.flowable_client import FlowableClient

log = logging.getLogger("clew.worker.incident")
PROCESS_KEY = "incident-recall"


def _flowable() -> FlowableClient:
    s = get_settings()
    return FlowableClient(s.flowable_url, s.flowable_user, s.flowable_password)


def business_key(incident_id) -> str:
    return f"incident:{incident_id}"


TASKS_DONE_BY_STATUS = {
    IncidentStatus.CONTAINED: ("qa_triage",),
    IncidentStatus.CLOSED: ("qa_triage", "director_escalation", "close_approval"),
}


def _complete_tasks(flowable: FlowableClient, incident_id, instance_id: str, task_keys) -> None:
    for task_key in task_keys:
        for task in flowable.tasks(instance_id, task_key):
            flowable.complete_task(task["id"])
            log.info("incident %s: completed %s", incident_id, task_key)


def _sync_with_status(flowable: FlowableClient, incident: Incident, instance_id: str) -> None:
    """Complete the tasks the incident's CURRENT status implies. Call AFTER starting the process."""
    _complete_tasks(flowable, incident.id, instance_id, TASKS_DONE_BY_STATUS.get(incident.status, ()))


def _complete_if_open(incident_id, task_key: str) -> None:
    with _flowable() as flowable:
        instance = flowable.find_process_instance(PROCESS_KEY, business_key(incident_id))
        if instance is None:
            return  # whoever starts the process syncs it with the incident's status
        _complete_tasks(flowable, incident_id, instance["id"], (task_key,))


def _start(flowable: FlowableClient, incident: Incident) -> dict:
    return flowable.start_process(
        PROCESS_KEY,
        business_key(incident.id),
        {"incidentId": str(incident.id), "triageSla": get_settings().incident_triage_sla},
    )


@handles("incident.opened")
def start_incident_process(message: OutboxMessage) -> None:
    incident_id = uuid.UUID(message.payload["incident_id"])
    with new_session() as session:
        incident = session.get(Incident, incident_id)
        if incident is None or incident.status == IncidentStatus.CLOSED:
            return  # nothing to run for an incident that is gone or already finished
        with _flowable() as flowable:
            instance = _start(flowable, incident)
            session.refresh(incident)  # status read AFTER the start: nothing slips in between
            _sync_with_status(flowable, incident, instance["id"])
        if incident.process_instance_id != instance["id"]:
            incident.process_instance_id = instance["id"]
            session.commit()


@handles("incident.suspects_confirmed")
def complete_triage(message: OutboxMessage) -> None:
    _complete_if_open(message.payload["incident_id"], "qa_triage")


@handles("incident.closed")
def complete_close(message: OutboxMessage) -> None:
    for task in TASKS_DONE_BY_STATUS[IncidentStatus.CLOSED]:  # ends the process, no stale tasks
        _complete_if_open(message.payload["incident_id"], task)


@handles("lock.applied")
def create_recall_notices(message: OutboxMessage) -> None:
    incident_id = uuid.UUID(message.payload["incident_id"])
    with new_session() as session:
        count = upsert_notices(session, incident_id, (message.payload["audit_seq"], message.payload["audit_hash"]))
        session.commit()
    log.info("incident %s: %d recall notice(s)", incident_id, count)


@reconciler
def reconcile_incident_processes() -> None:
    with new_session() as session:
        start_pending = exists().where(
            OutboxEvent.event_type == "incident.opened",
            OutboxEvent.aggregate_id == Incident.id,
            OutboxEvent.processed_at.is_(None),
            OutboxEvent.failed_at.is_(None),
        )  # the handler still owns the start: never race it into two processes for one business key
        incidents = session.scalars(
            select(Incident).where(Incident.status != IncidentStatus.CLOSED, ~start_pending)
        ).all()
        if not incidents:
            return
        with _flowable() as flowable:
            for incident in incidents:
                instance = _start(flowable, incident)
                session.refresh(incident)
                _sync_with_status(flowable, incident, instance["id"])
                incident.process_instance_id = instance["id"]
                if not incident.escalated and flowable.tasks(instance["id"], "director_escalation"):
                    incident.escalated = True
                    log.info("incident %s escalated to director (triage SLA missed)", incident.code)
        session.commit()


@reconciler
def reconcile_missing_notices() -> None:
    with new_session() as session:
        for incident_id in points_missing_notice(session):
            upsert_notices(session, incident_id)
            log.warning("incident %s: created notices missed earlier", incident_id)
        session.commit()
