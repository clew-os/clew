# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Recall latency over 20 runs against the running stack, through the gateway.

Not part of `make test-integration`; run it on a quiet stack with `make perf`
(= `pytest -m perf -s`). Every run is a fresh incident on its own scene (4 delivery points,
8 shipments), closed with four-eyes when its scene is dropped, so no open incident piles up in Flowable.

  commit  = confirm-suspects request -> response (lock + held shipments committed), client side
  notices = confirm-suspects request -> every recall notice visible (GET incident, polled every 1 s)
Targets: commit p95 <= 1 s, notices p95 <= 5 s.
"""

import math
import time

import pytest

from tests.integration.recall_scene import (
    call,
    incident_detail,
    open_incident,
    recall_scene,
    wait_for,
)

pytestmark = [pytest.mark.integration, pytest.mark.perf]

RUNS = 20
POINTS = 4
POLL_SECONDS = 1.0
COMMIT_P95_TARGET_S = 1.0
NOTICES_P95_TARGET_S = 5.0


def percentile(values: list[float], pct: float) -> float:
    """Nearest rank: the smallest value with at least `pct` percent of the samples at or below it."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)]


def summary(label: str, values: list[float]) -> str:
    p50, p95, worst = percentile(values, 50), percentile(values, 95), max(values)
    return f"{label:<8} p50 {p50:6.3f} s   p95 {p95:6.3f} s   max {worst:6.3f} s"


def test_confirm_suspects_commit_and_notice_latency(session_factory, owner_engine):
    # Warm-up (tokens, connection pools, JIT): not measured.
    with recall_scene(session_factory, owner_engine, POINTS) as warm:
        warm_incident = open_incident("Perf warm-up", warm)
        call("POST", f"/incidents/{warm_incident['id']}/confirm-suspects", "qa-lan", json=_body(warm))
        wait_for(lambda: len(incident_detail(warm_incident["id"])["notices"]) == POINTS, 30, "warm-up notices")

    commits: list[float] = []
    notices: list[float] = []
    server_ms: list[float] = []
    for n in range(RUNS):
        with recall_scene(session_factory, owner_engine, POINTS) as scene:
            incident = open_incident(f"Perf run {n + 1}", scene)
            started = time.monotonic()
            res = call("POST", f"/incidents/{incident['id']}/confirm-suspects", "qa-lan", json=_body(scene))
            commits.append(time.monotonic() - started)
            assert res.status_code == 200, res.text
            assert len(res.json()["held_shipments"]) == POINTS
            server_ms.append(res.json()["elapsed_ms"] / 1000)
            wait_for(
                lambda iid=incident["id"]: len(incident_detail(iid)["notices"]) == POINTS,
                30,
                f"run {n + 1}: every notice",
                POLL_SECONDS,
            )
            notices.append(time.monotonic() - started)

    print(f"\nrecall latency, N={RUNS}, {POINTS} delivery points per incident")
    for line in (summary("commit", commits), summary("server", server_ms), summary("notices", notices)):
        print(line)
    assert percentile(commits, 95) <= COMMIT_P95_TARGET_S, "commit p95 over target"
    assert percentile(notices, 95) <= NOTICES_P95_TARGET_S, "notices p95 over target"


def _body(scene) -> dict:
    return {"nodes": [{"type": "batch", "id": str(scene.batch_id)}], "lock_lots": False}
