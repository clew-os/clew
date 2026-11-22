# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Retry resets only failed outbox events (state rules, no database needed)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import AppError
from app.models.platform import OutboxEvent

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def _event(**kw) -> OutboxEvent:
    base = {"event_type": "x", "payload": {}, "attempts": 0}
    return OutboxEvent(**{**base, **kw})


def test_failed_event_becomes_deliverable_again():
    from app.services.admin_outbox import reset_failed_event

    event = _event(attempts=9, failed_at=NOW - timedelta(hours=1), claimed_until=NOW, last_error="boom")
    reset_failed_event(event, NOW)
    assert event.failed_at is None and event.attempts == 0
    assert event.next_attempt_at == NOW and event.claimed_until is None


@pytest.mark.parametrize(
    "state", [{}, {"processed_at": NOW}, {"processed_at": NOW, "failed_at": NOW - timedelta(hours=1)}]
)
def test_only_failed_events_can_be_retried(state):
    from app.services.admin_outbox import reset_failed_event

    with pytest.raises(AppError) as err:
        reset_failed_event(_event(**state), NOW)
    assert err.value.status == 409
