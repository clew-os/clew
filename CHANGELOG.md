<!--
SPDX-FileCopyrightText: The Clew Authors
SPDX-License-Identifier: Apache-2.0
-->

# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.9.0] - 2026-11-22

First tagged release: feature complete for the contest scope.

### Changed
- The project is now called **Clew** (was the working name `metrace`): realm `clew`, clients
  `clew-web`, `clew-cli`, `clew-api`, `clew-test`, CLI command `clew`, database and roles `clew*`,
  compose project and images `clew`, `.env` keys `CLEW_*` (run `make reset` on an old checkout).
- Business routes still never call Flowable; the API now also reads it from the sysadmin endpoints.

### Added
- Tier-1 admin plane (`docs/admin-guide.md`): a second gateway listener `127.0.0.1:9081` that
  routes only the Keycloak admin console of realm `clew` (own admin hostname; the public
  listener denies `/auth/admin/*`, the master realm is routed nowhere); SeaweedFS master and
  filer UIs opt-in for maintenance (`make admin-tools-open`); APISIX Control API on the
  internal network only. Keycloak login and admin events are recorded (30 days).
- Platform role `sysadmin` and demo account `sysadmin-khoa`: reaches `/api/v1/admin/*` only,
  no business data; least-privilege console grants for realm `clew` (no impersonation).
- Clew core admin (`/admin` in the web app, `/api/v1/admin/*`): health of every core service,
  Flowable definitions, instances, tasks, timers and dead-letter retry, outbox backlog and retry,
  gateway routes (plugin names only). Admin retries are written to the audit chain.
- Repository skeleton: Apache-2.0, REUSE metadata, AUTHORS, CI (ruff, reuse lint, gitleaks, unit tests).
- `make init` generates local secrets into `.env`; compose refuses to start without it.
- Keycloak 26.8 (official image) with admin/account consoles disabled at build time.
- Realm `clew`: roles, clients (web PKCE, CLI device flow, sensor client credentials), customer organizations.
- APISIX standalone gateway: `/auth` allowlist, `/api` JWT verification (JWKS), per-token rate limits.
- API: JWT re-verification, `GET /api/v1/whoami`.
- Flowable 8 REST client: idempotent deploy, idempotent start by business key, external-worker jobs, tasks.
- Compose stack with SeaweedFS (S3), one-shot `migrate` (Alembic + bucket), outbox `worker`, static `web`.
- Common error envelope with reason codes and request id; default-deny routers (internal, portal, sensor)
  enforced by a test that walks every route.
- Tamper-evident audit hash chain with anchor verification; runtime DB role cannot UPDATE/DELETE it.
- Transactional outbox and worker loop (claim, handle outside the transaction, mark; backoff; failure cap),
  heartbeat healthcheck, reconciler loop, idempotent BPMN deployment.
- File upload/download through the API only: magic-byte allow-list (JPEG, PNG, PDF), size cap,
  content-addressed storage, ownership per customer organization (other org gets 404).
- `scripts/smoke-core.sh` and a compose-smoke CI workflow (every PR, nightly, fresh volumes).
- Domain model (migrations 0002–0003): suppliers and certificates, receiving (Mẫu 1), lots, dishes,
  menus, cooking batches (Mẫu 2) with lot or intermediate-batch inputs, portion checks (Mẫu 3),
  retained samples, shipments, complaints, incidents, per-incident locks, four-eyes close requests,
  recall notices, Poka-yoke thresholds with their basis.
- `lineage_edge` view and `GET /api/v1/lineage/{type}/{id}?direction=forward|backward|both`
  (recursive CTE, cycle guard, depth/node caps, `truncated` flag, lock state, portions per point).
- Read-only master data endpoints (suppliers with certificate state, ingredients, dishes,
  delivery points, assets, menus, thresholds).
- One-shot `seed`: synthetic DEMO master data and two service days relative to now.
- `docs/domain-model.md`, `make openapi`.

- Poka-yoke rules P1–P4 as pure functions with thresholds that carry their basis
  (law/guidance/field/internal); every block answers 422 with all violations and is logged.
- Kitchen flow API: receiving (Mẫu 1), cooking batches with inputs and finish (Mẫu 2), retained
  samples with QR seal, portion checks (Mẫu 3), shipments with live blockers, dispatch,
  meal-service checklist (state machine in the API, no BPMN).
- Lock guards (one advisory lock, lineage-based, fail closed) wired into inputs, finish, add-item,
  dispatch and sample discard.
- `make demo-reset`: fresh "today" in about 10 seconds; seeded receivings carry delivery notes.
- `docs/poka-yoke-rules.md`.
- Incidents: complaints (internal channel), #3 cluster suggestions (SQL, QA confirms), incidents,
  confirm suspects => per-incident locks applied in one transaction (pending shipments held,
  fail closed on incomplete lineage), four-eyes close (approver role, different person),
  each incident releases only its own locks.
- Worker: BPMN `incident-recall` (triage SLA timer escalates to the director), idempotent process
  start by business key, recall notices per delivery point carrying the audit anchor,
  reconcilers for missing processes, escalation flags and missed notices.
- `outbreak` seed scenario; `GET /api/v1/lots`.
- Customer portal API (`/api/v1/portal/*`): deliveries, complaints (create/list), recall notices
  (list/acknowledge), scoped by the organizations in the token; references to another
  organization's delivery point or file answer 404.
- P6: complaint answer deadline from the customer profile (`sla_hours`), worker sweep flags
  overdue complaints (no BPMN).
- Customer differences (school vs factory) are profile data, not code branches.
- CLI `clew` (device-flow login, staff only, `whoami`, `trace`, `shipments list`, `incidents list`);
  lineage accepts business codes as well as UUIDs.
- Cold chain: sensor gateway machine identity may only report its own assets (claim), device clock
  skew is rejected, N consecutive out-of-band readings open one alert per asset and start the
  `cold-chain-alert` process (QA check, director escalation); alert shows lots and retained samples
  in that fridge. `tools/sensor-simulator` (normal/drift/breach).
- #6 audit verification: `GET /api/v1/audit/verify?anchor_seq=&anchor_hash=` and `GET /api/v1/audit/head`.

- Incident report drafts by a local LLM (Ollama, optional; deterministic template otherwise),
  edited and approved by QA; `scripts/ai-up.sh`.
- #1 Mẫu 2 as PDF (`GET /api/v1/forms/2/{batch_id}.pdf`, Noto Sans OFL-1.1) with the audit anchor in the footer.
- #2 recall drill (`POST /api/v1/recall-drills`, `clew drill run`): trace, lock preview in a
  rolled-back savepoint, portion coverage, recorded in the audit chain.

- Web screens: complaints with cluster suggestions and SLA countdowns, incident board and detail
  (confirm suspects, affected shipments, four-eyes close, report draft), trace table and graph
  (Cytoscape.js), cold-chain banner with sparkline, audit verification; mobile-first customer portal
  (deliveries, complaints with photos, recall notices with acknowledgement and audit anchor).

### Fixed
- Receiving and incident codes no longer collide under concurrent requests.

### Security
- `clew-web` and `clew-cli` tokens map only app roles (full scope off), so they never carry
  Keycloak admin roles.
- Error texts shown on the admin pages are sanitised (no credentials, SQL or parameters).
- The CI-only `clew-test` client only exists when `KC_OVERLAYS=test`; demos remove it.
