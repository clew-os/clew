# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Core-status aggregator: concurrency, one failing/slow probe never breaks the rest, no secrets leak."""

import time

from app.services.admin_core_status import Probe, ProbeResult, run_probes, safe_error


def _ok(**facts):
    return lambda: ProbeResult("up", facts)


def _boom():
    raise RuntimeError("connect to http://admin:hunter2@db:5432 failed " + "x" * 400)


def _slow():
    time.sleep(1.5)
    return ProbeResult("up", {})


def test_failing_probe_is_down_others_stay_up_and_order_is_kept():
    probes = [
        Probe("a", "A", "structured_data", _ok(version="17")),
        Probe("b", "B", "sso", _boom, console_url="http://localhost:9081/"),
        Probe("c", "C", "gateway", _ok(routes=5)),
    ]
    out = run_probes(probes, deadline_s=2)
    assert [c.key for c in out] == ["a", "b", "c"]
    assert [c.status for c in out] == ["up", "down", "up"]
    assert out[0].facts == {"version": "17"}
    assert out[1].console_url == "http://localhost:9081/"
    error = out[1].facts["error"]
    assert len(error) <= 200 and "hunter2" not in error and error.startswith("RuntimeError")


def test_slow_probe_is_reported_down_at_the_deadline_without_blocking():
    started = time.monotonic()
    out = run_probes([Probe("s", "S", "workflow", _slow), Probe("f", "F", "platform", _ok())], deadline_s=0.2)
    assert time.monotonic() - started < 1.0
    assert out[0].status == "down" and "timeout" in str(out[0].facts["error"])
    assert out[1].status == "up"


def test_probes_run_concurrently():
    def nap():
        time.sleep(0.3)
        return ProbeResult("up", {})

    started = time.monotonic()
    out = run_probes([Probe(str(i), "n", "platform", nap) for i in range(5)], deadline_s=2)
    assert all(c.status == "up" for c in out)
    assert time.monotonic() - started < 1.0


def test_degraded_status_and_latency_are_passed_through():
    out = run_probes([Probe("d", "D", "platform", lambda: ProbeResult("degraded", {"failed": 2}))], deadline_s=1)
    assert out[0].status == "degraded" and out[0].latency_ms >= 0


def test_safe_error_strips_url_credentials_and_caps_length():
    text = safe_error(ValueError("postgresql://user:pw@host/db " + "y" * 500))
    assert "pw" not in text and "://***@" in text and len(text) == 200
