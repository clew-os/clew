# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Sysadmin view of the transactional outbox and the manual retry of failed events."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.audit_hash_chain import append_audit
from app.core.error_text import sanitize_error_text
from app.core.errors import AppError, not_found
from app.core.reason_codes import ReasonCode
from app.models.platform import OutboxEvent
from app.schemas.admin import FailedOutboxEventOut, OutboxOverviewOut

FAILED_LIST_LIMIT = 20
ERROR_MAX_CHARS = 300


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def outbox_overview(session: Session) -> OutboxOverviewOut:
    pending = OutboxEvent.processed_at.is_(None) & OutboxEvent.failed_at.is_(None)
    counts = session.execute(
        select(
            func.count().filter(pending),
            func.count().filter(OutboxEvent.processed_at.is_not(None)),
            func.count().filter(OutboxEvent.failed_at.is_not(None)),
            # Only events that are due count as "waiting": a retry scheduled for later is not stuck.
            func.extract(
                "epoch",
                func.now()
                - func.min(OutboxEvent.created_at).filter(pending, OutboxEvent.next_attempt_at <= func.now()),
            ),
            func.max(OutboxEvent.processed_at),
        )
    ).one()
    failed = session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.failed_at.is_not(None))
        .order_by(OutboxEvent.failed_at.desc())
        .limit(FAILED_LIST_LIMIT)
    ).all()
    return OutboxOverviewOut(
        pending=counts[0],
        processed=counts[1],
        failed=counts[2],
        oldest_pending_age_s=max(0, int(counts[3])) if counts[3] is not None else None,
        last_processed_at=_iso(counts[4]),
        failed_events=[
            FailedOutboxEventOut(
                id=e.id,
                event_type=e.event_type,
                attempts=e.attempts,
                failed_at=_iso(e.failed_at),
                last_error=sanitize_error_text(e.last_error or "", ERROR_MAX_CHARS) or None,
            )
            for e in failed
        ],
    )


def reset_failed_event(event: OutboxEvent, now: datetime | ColumnElement[datetime]) -> None:
    """Make a failed, unprocessed event deliverable again (409 otherwise). `now` may be a SQL
    expression (func.now()) so the database clock decides, like everywhere else in the outbox."""
    if event.failed_at is None or event.processed_at is not None:
        raise AppError(409, ReasonCode.CONFLICT, "Event is not in the failed state")
    event.failed_at = None
    event.attempts = 0
    event.next_attempt_at = now
    event.claimed_until = None


def retry_failed_event(session: Session, event_id: int, actor: str) -> None:
    event = session.get(OutboxEvent, event_id, with_for_update=True)
    if event is None:
        raise not_found("Outbox event")
    reset_failed_event(event, func.now())
    append_audit(
        session,
        actor=actor,
        action="admin.outbox.retry",
        entity_type="outbox_event",
        entity_id=event_id,
        payload={"event_type": event.event_type},
    )
    session.commit()
