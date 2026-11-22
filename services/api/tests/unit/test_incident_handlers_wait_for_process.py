# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Incident/alert task handlers with a stand-in Flowable: no process yet, finished process, and
the sync-with-current-status rule the starters apply (no real Flowable needed)."""

from types import SimpleNamespace

from app.models.coldchain import AlertStatus
from app.models.enums import IncidentStatus
from app.worker import coldchain_handlers, incident_handlers
from app.worker.handler_registry import OutboxMessage


class FakeFlowable:
    def __init__(self, instance, open_tasks):
        self.instance, self.open_tasks, self.completed = instance, open_tasks, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def find_process_instance(self, key, business_key):
        return self.instance

    def tasks(self, instance_id, task_key):
        return [t for t in self.open_tasks if t["key"] == task_key and t["id"] not in self.completed]

    def complete_task(self, task_id):
        self.completed.append(task_id)


def _message(event_type: str) -> OutboxMessage:
    return OutboxMessage(1, event_type, "incident", None, {"incident_id": "i1", "alert_id": "a1"}, 1)


def _tasks(*keys):
    return [{"key": k, "id": f"t-{k}"} for k in keys]


def test_events_return_quietly_while_no_process_exists(monkeypatch):
    fake = FakeFlowable(None, [])
    monkeypatch.setattr(incident_handlers, "_flowable", lambda: fake)
    monkeypatch.setattr(coldchain_handlers, "_flowable", lambda: fake)
    incident_handlers.complete_triage(_message("incident.suspects_confirmed"))
    incident_handlers.complete_close(_message("incident.closed"))
    coldchain_handlers.complete_fridge_check(_message("coldchain.acknowledged"))
    assert fake.completed == []  # the later starter syncs the process with the status


def test_events_on_a_finished_process_do_nothing(monkeypatch):
    fake = FakeFlowable({"id": "p1"}, [])  # history finds it, no task is open
    monkeypatch.setattr(incident_handlers, "_flowable", lambda: fake)
    monkeypatch.setattr(coldchain_handlers, "_flowable", lambda: fake)
    incident_handlers.complete_triage(_message("incident.suspects_confirmed"))
    incident_handlers.complete_close(_message("incident.closed"))
    coldchain_handlers.complete_fridge_check(_message("coldchain.acknowledged"))
    assert fake.completed == []


def test_suspects_confirmed_completes_only_the_triage_task(monkeypatch):
    fake = FakeFlowable({"id": "p1"}, _tasks("qa_triage", "close_approval"))
    monkeypatch.setattr(incident_handlers, "_flowable", lambda: fake)
    incident_handlers.complete_triage(_message("incident.suspects_confirmed"))
    assert fake.completed == ["t-qa_triage"]


def test_close_completes_every_open_task(monkeypatch):
    fake = FakeFlowable({"id": "p1"}, _tasks("qa_triage", "director_escalation", "close_approval"))
    monkeypatch.setattr(incident_handlers, "_flowable", lambda: fake)
    incident_handlers.complete_close(_message("incident.closed"))
    assert sorted(fake.completed) == ["t-close_approval", "t-director_escalation", "t-qa_triage"]


def test_starter_sync_follows_the_incident_status():
    open_tasks = _tasks("qa_triage", "director_escalation", "close_approval")
    for status, expected in (
        (IncidentStatus.OPEN, []),
        (IncidentStatus.CONTAINED, ["t-qa_triage"]),
        (IncidentStatus.CLOSED, ["t-qa_triage", "t-director_escalation", "t-close_approval"]),
    ):
        fake = FakeFlowable({"id": "p1"}, open_tasks)
        incident_handlers._sync_with_status(fake, SimpleNamespace(id="i1", status=status), "p1")
        assert sorted(fake.completed) == sorted(expected), status


def test_cold_chain_sync_completes_fridge_tasks_for_an_acknowledged_alert():
    fake = FakeFlowable({"id": "p1"}, _tasks("qa_check_fridge", "director_escalation"))
    coldchain_handlers._complete_tasks(fake, "p1")
    assert sorted(fake.completed) == ["t-director_escalation", "t-qa_check_fridge"]
    assert AlertStatus.ACKNOWLEDGED == "acknowledged"
