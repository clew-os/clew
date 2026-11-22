<!--
SPDX-FileCopyrightText: The Clew Authors
SPDX-License-Identifier: Apache-2.0
-->

# Workflows (Flowable)

Only processes that need **timers and people** run in Flowable. The kitchen
flow is a state machine in the API, and incident status is owned by the API.
Only the worker drives Flowable. An API action writes an outbox event in the same
transaction; the worker handles it after commit, so a Flowable outage delays
workflow steps but never blocks the kitchen or a recall. Business routes never
call Flowable; the sysadmin endpoints (`/api/v1/admin/workflow`) only read it and
move dead-letter jobs back to the queue (see [admin-guide.md](admin-guide.md)).

Files live in `workflows/bpmn/` and are deployed by the worker at start-up.
Deployment is idempotent: the deployment name embeds a hash of the file, so an
unchanged file never creates a new process version.

## incident-recall

```
start ─► [qa_triage] ───────────────► [close_approval] ─► end
            ╎ timer ${triageSla} (non-interrupting)
            └► [director_escalation] ─► end
```

| Step | Who | Completed when |
|---|---|---|
| `qa_triage` | QA | Suspects are confirmed and locked (`incident.suspects_confirmed`) |
| `director_escalation` | Director | Created when the triage SLA passes. Shown as a red "escalated" flag on the incident. Completed when the incident closes |
| `close_approval` | Approver | Completed when the incident closes, i.e. the approver approved the close request (requester ≠ approver, enforced by the API) |

Business key `incident:<id>`. Variables: `incidentId`, `triageSla`
(`INCIDENT_TRIAGE_SLA`, default `PT30M`, demo `PT1M`). A reconciler (every 30 s)
starts the process for any open incident that lacks one and mirrors the escalation.

**Start syncs with the business state.** Whoever starts a process (the `incident.opened`
handler or the reconciler) reads the incident's *current* status right after the start and
completes the tasks it implies: contained means `qa_triage` is done, closed means every task
is done (a closed incident without a process is not started at all). So an event that arrived
while no process existed returns quietly instead of retrying: the triage SLA timer can never
escalate an incident that was contained during an outage. The reconciler skips incidents whose
`incident.opened` event is still pending in the outbox, so handler and reconciler never start
two processes for one business key.

**Flowable outage.** The API never calls Flowable, so locks, held shipments and recall notices
commit as usual. Outbox events that need Flowable fail with an infrastructure error and retry
with backoff (2 s doubling to 60 s), never `failed`; the sysadmin core-status page shows
Flowable `down`. When Flowable returns, the process is started and synced as above and the
outbox drains. Tested by `tests/integration/test_worker_survives_flowable_outage.py`.

## cold-chain-alert

```
start ─► [qa_check_fridge] ─► end
            ╎ timer ${checkSla} (non-interrupting)
            └► [director_escalation] ─► end
```

Started when a fridge reports `coldchain_consecutive_n` consecutive readings
outside its safe band (seeded at 3). Readings whose device clock is more than
`coldchain_max_skew_s` (60 s) away from server time are rejected. One open
alert per asset. Business key `coldchain:<alert id>`. Variables: `assetCode`,
`checkSla` (`COLDCHAIN_CHECK_SLA`, default `PT10M`).

QA acknowledging the alert in the app completes `qa_check_fridge` and any open
`director_escalation`. The same start-syncs-with-state rule applies: an alert acknowledged while
Flowable was down gets no process, or its tasks are completed right after the start; the
reconciler skips alerts whose `coldchain.breach` event is still pending.

## Callbacks

Flowable never calls Clew. The worker calls the Flowable REST API to start
processes and to complete tasks, keyed by business key, so Flowable needs
neither the app's URL nor any credential of it.
