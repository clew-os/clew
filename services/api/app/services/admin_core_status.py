# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Aggregates health probes of the tier-1 components. Probes run concurrently, each under a deadline;
a probe that raises or hangs turns only its own component "down" (short, credential-free error)."""

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass

from app.core.error_text import sanitize_error_text
from app.schemas.admin import ComponentStatus, CoreComponentOut, ServiceKind

ERROR_MAX_CHARS = 200


@dataclass(frozen=True)
class ProbeResult:
    status: ComponentStatus
    facts: dict[str, object]


@dataclass(frozen=True)
class Probe:
    key: str
    label: str
    service_kind: ServiceKind
    run: Callable[[], ProbeResult]
    console_url: str | None = None
    secondary_console_url: str | None = None


def safe_error(exc: BaseException) -> str:
    """Class name plus message through the shared sanitiser. Never the repr of a request."""
    return sanitize_error_text(f"{type(exc).__name__}: {exc}".strip(": "), ERROR_MAX_CHARS)


def _component(probe: Probe, result: ProbeResult, started: float) -> CoreComponentOut:
    return CoreComponentOut(
        key=probe.key,
        label=probe.label,
        service_kind=probe.service_kind,
        status=result.status,
        latency_ms=round((time.monotonic() - started) * 1000),
        facts=result.facts,
        console_url=probe.console_url,
        secondary_console_url=probe.secondary_console_url,
    )


def _timed(probe: Probe) -> CoreComponentOut:
    started = time.monotonic()
    try:
        return _component(probe, probe.run(), started)
    except Exception as exc:  # one broken probe must never break the page
        return _component(probe, ProbeResult("down", {"error": safe_error(exc)}), started)


def run_probes(probes: list[Probe], deadline_s: float) -> list[CoreComponentOut]:
    """Results keep the order of `probes`. A probe still running at the deadline is reported down."""
    started = time.monotonic()
    executor = ThreadPoolExecutor(max_workers=max(1, len(probes)), thread_name_prefix="admin-probe")
    try:
        futures = [executor.submit(_timed, probe) for probe in probes]
        wait(futures, timeout=deadline_s)
        out = []
        for probe, future in zip(probes, futures, strict=True):
            if future.done():
                out.append(future.result())
            else:
                result = ProbeResult("down", {"error": f"timeout after {deadline_s:g}s"})
                out.append(_component(probe, result, started))
        return out
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


class SingleFlightCache:
    """Share one computation between concurrent callers and reuse its result for `ttl_s` seconds,
    so a page polling every 10 s from several browsers never multiplies probe traffic."""

    def __init__(self, ttl_s: float):
        self._ttl_s = ttl_s
        self._lock = threading.Lock()
        self._value: list[CoreComponentOut] | None = None
        self._expires = 0.0

    def get(self, compute: Callable[[], list[CoreComponentOut]]) -> list[CoreComponentOut]:
        with self._lock:  # held while computing: callers arriving meanwhile wait, then hit the cache
            if self._value is None or time.monotonic() >= self._expires:
                self._value = compute()
                self._expires = time.monotonic() + self._ttl_s
            return self._value
