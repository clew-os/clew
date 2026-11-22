<!--
SPDX-FileCopyrightText: The Clew Authors
SPDX-License-Identifier: Apache-2.0
-->

# Performance

Measured numbers for the claims the demo makes. Re-run before a release; numbers from another machine are not comparable.

## Recall latency (issue #1)

What the QA officer feels after pressing "confirm suspects":

| Metric | Definition | Target |
| --- | --- | --- |
| commit | `POST /incidents/{id}/confirm-suspects` request to response through the gateway: lock and held shipments committed | p95 <= 1 s |
| notices | same request start until every recall notice is visible in `GET /incidents/{id}` (polled every 1 s) | p95 <= 5 s |

`server` is the `elapsed_ms` the API reports for the lock transaction alone.

### Result

| | |
| --- | --- |
| Date | 2026-11-22 |
| Machine | Colima (vz), 4 CPU / 6 GB, Apple Silicon (arm64) |
| Stack | `make dev-ports`, idle, worker + Flowable running |
| Runs | N = 20 (after one warm-up run), each a fresh incident |
| Scene | one batch, 4 delivery points, per point 1 planned (held) + 1 dispatched (recalled) shipment |

| | p50 | p95 | max | target | met |
| --- | --- | --- | --- | --- | --- |
| commit (client) | 0.017 s | 0.020 s | 0.024 s | p95 <= 1 s | yes |
| commit (server `elapsed_ms`) | 0.005 s | 0.005 s | 0.006 s | | |
| notices | 1.057 s | 1.158 s | 2.064 s | p95 <= 5 s | yes |

A second identical run gave notices p50 1.060 s / p95 2.074 s / max 2.081 s: with N=20 the p95 is the 19th value, so one slow poll moves it between about 1 s and 2 s.

Reading the notices number: the first poll comes right after the request returns and the next one a second later, so the figure is the time of the first poll that sees the notices. The notices themselves exist within about 1 s (the worker's outbox lane wakes every 1 s when idle), so the real latency is at most 1 s and p50 is simply the second poll; a 1 s poll cannot resolve anything finer. Only the demo scene size was measured; a lineage with hundreds of shipments is not covered.

### How to run

```bash
make dev-ports     # stack up with postgres published on 127.0.0.1 (needs .env)
make perf          # = cd services/api && uv run pytest -m perf -s
```

About 30 s. The test (`services/api/tests/integration/test_perf_recall_latency.py`) goes through the gateway, builds its own private scene in the dev database for every run and deletes it afterwards (no `demo-reset` needed, demo data untouched), closes each incident with four-eyes afterwards, prints p50/p95/max and fails when a p95 target is missed. It is marked `perf`: it runs only with `-m perf` or `make perf`, and is reported as skipped by a plain `pytest` or `make test-integration`. Run it on a quiet stack: a concurrent `make test-integration` skews the numbers.

## Flowable outage (issue #2)

Not a latency figure but a behaviour that was measured: with Flowable stopped for 60 s, locking, holding and recall notices still commit on the API side; `incident.*` outbox events stay pending with growing `attempts` (backoff 2 s ... 60 s, never `failed`) and the process is started later by the `incident.opened` handler or the reconciler, which then completes the tasks the incident's current status implies (see `docs/bpmn.md`); `core-status` reports Flowable `down`. After `docker compose start flowable` the process is created, the outbox drains and `core-status` returns to `up` (about 1-2 minutes including Flowable boot and the worker's backoff). Test: `services/api/tests/integration/test_worker_survives_flowable_outage.py` (marker `outage`, part of `make test-integration`, about 2 minutes).
