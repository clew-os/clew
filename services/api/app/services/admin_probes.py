# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""The concrete probes of the tier-1 components, built from settings. Each returns a ProbeResult
or raises; app.services.admin_core_status turns exceptions into a "down" component."""

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit_hash_chain import chain_head
from app.core.database import new_session
from app.core.object_storage import head_bucket_quick
from app.core.settings import Settings
from app.services.admin_core_status import Probe, ProbeResult
from app.services.admin_gateway import gateway_overview
from app.services.admin_outbox import outbox_overview
from app.services.admin_workflow import admin_flowable_client

OUTBOX_STUCK_AFTER_S = 120


@contextmanager
def _bounded_session() -> Iterator[Session]:
    """Own session whose statements cannot hang the page: 2 s statement and lock timeouts."""
    with new_session() as session:
        session.execute(text("SET LOCAL statement_timeout = '2s'"))
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        yield session


def _json(settings: Settings, url: str) -> dict:
    res = httpx.get(url, timeout=settings.admin_probe_timeout_s)
    res.raise_for_status()
    body = res.json()
    return body if isinstance(body, dict) else {}


def _postgres(_: Settings) -> ProbeResult:
    with _bounded_session() as session:
        version = session.scalar(text("SELECT version()")) or ""
        size = session.scalar(text("SELECT pg_database_size(current_database())"))
    return ProbeResult("up", {"version": " ".join(version.split()[:2]), "db_size_mb": round((size or 0) / 1048576, 1)})


def _keycloak(settings: Settings) -> ProbeResult:
    realm = _json(settings, f"{settings.keycloak_internal_url.rstrip('/')}/realms/{settings.keycloak_realm}")
    facts: dict[str, object] = {"realm": realm.get("realm")}
    try:
        ready = _json(settings, f"{settings.keycloak_management_url.rstrip('/')}/health/ready").get("status")
    except (httpx.HTTPError, ValueError):
        ready = "unreachable"
    facts["readiness"] = ready
    return ProbeResult("up" if ready == "UP" else "degraded", facts)


def _apisix(_: Settings) -> ProbeResult:
    overview = gateway_overview()
    return ProbeResult("up", {"routes": len(overview.routes), "upstreams": len(overview.upstreams)})


def _seaweedfs(settings: Settings) -> ProbeResult:
    cluster = _json(settings, f"{settings.seaweedfs_master_url.rstrip('/')}/cluster/status")
    bucket_ok = head_bucket_quick(settings.admin_probe_timeout_s)
    facts = {"leader": cluster.get("Leader"), "bucket": settings.s3_bucket, "bucket_reachable": bucket_ok}
    return ProbeResult("up" if cluster.get("IsLeader") is not None and bucket_ok else "degraded", facts)


def _flowable(_: Settings) -> ProbeResult:
    with admin_flowable_client() as flowable:
        engine = flowable.engine_info()
    return ProbeResult("up", {"engine": engine.get("name"), "version": engine.get("version")})


def _outbox(_: Settings) -> ProbeResult:
    with _bounded_session() as session:
        o = outbox_overview(session)
    facts = {
        "pending": o.pending,
        "failed": o.failed,
        "oldest_pending_age_s": o.oldest_pending_age_s,
        "last_processed_at": o.last_processed_at,
    }
    stuck = (o.oldest_pending_age_s or 0) > OUTBOX_STUCK_AFTER_S
    return ProbeResult("degraded" if o.failed > 0 or stuck else "up", facts)


def _audit(_: Settings) -> ProbeResult:
    with _bounded_session() as session:
        head = chain_head(session)
    return ProbeResult("up", {"head_seq": head[0] if head else None})


def build_probes(settings: Settings) -> list[Probe]:
    def bind(fn):
        return lambda: fn(settings)

    return [
        Probe("postgres", "PostgreSQL", "structured_data", bind(_postgres)),
        Probe("keycloak", "Keycloak (SSO)", "sso", bind(_keycloak), settings.keycloak_console_url),
        Probe("apisix", "APISIX (cổng API)", "gateway", bind(_apisix)),
        Probe(
            "seaweedfs",
            "SeaweedFS (S3)",
            "unstructured_data",
            bind(_seaweedfs),
            settings.seaweedfs_console_url,
            settings.seaweedfs_filer_console_url,
        ),
        Probe("flowable", "Flowable (quy trình)", "workflow", bind(_flowable)),
        Probe("outbox", "Outbox + worker", "platform", bind(_outbox)),
        Probe("audit", "Nhật ký kiểm toán", "platform", bind(_audit)),
    ]
