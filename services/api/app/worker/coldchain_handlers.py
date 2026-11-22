# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Cold-chain alerts in Flowable (`cold-chain-alert`): QA checks the fridge under a
timer that escalates to the director. Started/completed only by the worker.

Same rule as incidents: whoever starts a process then syncs it with the alert's CURRENT status
(acknowledged -> tasks done), and an alert acknowledged before any process existed gets none."""

import logging
import uuid

from sqlalchemy import exists, select

from app.core.database import new_session
from app.core.settings import get_settings
from app.models.coldchain import AlertStatus, ColdChainAlert
from app.models.kitchen_and_customers import Asset
from app.models.platform import OutboxEvent
from app.worker.handler_registry import OutboxMessage, handles, reconciler
from app.workflow.flowable_client import FlowableClient

log = logging.getLogger("clew.worker.coldchain")
PROCESS_KEY = "cold-chain-alert"


def _flowable() -> FlowableClient:
    s = get_settings()
    return FlowableClient(s.flowable_url, s.flowable_user, s.flowable_password)


FRIDGE_TASKS = ("qa_check_fridge", "director_escalation")  # no stale escalation task left behind


def _complete_tasks(flowable: FlowableClient, instance_id: str) -> None:
    for key in FRIDGE_TASKS:
        for task in flowable.tasks(instance_id, key):
            flowable.complete_task(task["id"])


def _start(flowable: FlowableClient, session, alert: ColdChainAlert, asset_code: str) -> str:
    instance = flowable.start_process(
        PROCESS_KEY, f"coldchain:{alert.id}", {"assetCode": asset_code, "checkSla": get_settings().coldchain_check_sla}
    )
    session.refresh(alert)  # status read AFTER the start: an acknowledgement in between is not lost
    if alert.status == AlertStatus.ACKNOWLEDGED:
        _complete_tasks(flowable, instance["id"])
    return instance["id"]


@handles("coldchain.breach")
def start_alert_process(message: OutboxMessage) -> None:
    with new_session() as session, _flowable() as flowable:
        alert = session.get(ColdChainAlert, uuid.UUID(message.payload["alert_id"]))
        if alert is None or alert.process_instance_id or alert.status != AlertStatus.OPEN:
            return  # an alert acknowledged during the outage never needs a process
        alert.process_instance_id = _start(flowable, session, alert, message.payload["asset"])
        session.commit()
        log.warning("cold-chain alert %s for %s: process started", alert.id, message.payload["asset"])


@handles("coldchain.acknowledged")
def complete_fridge_check(message: OutboxMessage) -> None:
    with _flowable() as flowable:
        instance = flowable.find_process_instance(PROCESS_KEY, f"coldchain:{message.payload['alert_id']}")
        if instance is None:
            return  # whoever starts the process syncs it with the alert's status
        _complete_tasks(flowable, instance["id"])


@reconciler
def reconcile_alert_processes() -> None:
    with new_session() as session:
        start_pending = exists().where(
            OutboxEvent.event_type == "coldchain.breach",
            OutboxEvent.aggregate_id == ColdChainAlert.id,
            OutboxEvent.processed_at.is_(None),
            OutboxEvent.failed_at.is_(None),
        )  # the handler still owns the start
        rows = session.execute(
            select(ColdChainAlert, Asset.code)
            .join(Asset, Asset.id == ColdChainAlert.asset_id)
            .where(
                ColdChainAlert.status == AlertStatus.OPEN,
                ColdChainAlert.process_instance_id.is_(None),
                ~start_pending,
            )
        ).all()
        if not rows:
            return
        with _flowable() as flowable:
            for alert, code in rows:
                alert.process_instance_id = _start(flowable, session, alert, code)
        session.commit()
