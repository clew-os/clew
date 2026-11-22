<!--
SPDX-FileCopyrightText: The Clew Authors
SPDX-License-Identifier: Apache-2.0
-->

# Architecture

Clew is the digital operating system of **one** catering company that cooks
meals for school canteens and factories. The central entity is the
**cooking batch**: every batch knows which ingredient lots went in and which
delivery points received it, so an incident can be traced back to suppliers and
the affected food can be locked everywhere within seconds.

## Tiers

| Tier | What | Components |
|---|---|---|
| 1. Headless core (platform) | Generic services, no business logic, with an admin UI for system admins | Keycloak (SSO), Apache APISIX (gateway), PostgreSQL + SeaweedFS (data), Flowable REST (workflow), plus generic API building blocks: audit hash chain, transactional outbox, file service. Admin plane: Keycloak admin console, SeaweedFS UIs, Clew core admin (`/admin`) |
| 2. Domain | Catering business rules | Clew API (FastAPI) + outbox worker |
| 3. Clients | People and machines | One web SPA (`/ops/*` for staff, `/portal/*` for customers, `/admin/*` for system admins), CLI, sensor simulator |

Tier 2 talks to Tier 1 only through documented interfaces: OIDC/JWKS
(Keycloak), SQL (PostgreSQL), S3 (SeaweedFS) and REST (Flowable). Clients
reach the system **only** through the gateway.

## Data flow

```
SPA ops/portal/admin─┐
CLI (device flow) ───┼─► APISIX 127.0.0.1:9080 ─┬─ /auth/* (allowlist) ─► Keycloak ─► PG db keycloak
sensor (client cred) ┘   OIDC/JWKS, rate limit  ├─ /api/*  ─► Clew API ─► PG db clew, SeaweedFS
                         per token, request id  └─ /       ─► web (static SPA)
                                                             │ outbox_event (same transaction)
                                                             ▼
                                         worker (claim → HTTP → mark) ─► Flowable REST ─► PG db flowable
```

- **One public origin.** Keycloak is served under `/auth` behind the gateway,
  so every token carries the same issuer (`http://localhost:9080/auth/realms/clew`)
  whether it was obtained by a browser, the CLI or a test. Services inside
  docker fetch keys from `http://keycloak:8080/auth/...` (back-channel).
- **Gateway allowlist.** Only login, token, device and discovery endpoints of
  realm `clew` are routed. Admin, master realm and account console paths
  have no route (404). The account console is disabled in the Keycloak build
  (`infra/keycloak/Dockerfile`: the official `quay.io/keycloak` image with
  build options); the admin console lives only on the admin plane (below).
- **Zero trust.** APISIX verifies the JWT, and the API verifies it again
  (signature via JWKS, issuer, audience `clew-api`, expiry). The API never
  trusts identity headers added by the gateway. Every route denies by default
  and requires an internal role, `customer_staff`, the `sensor` role or, for
  `/api/v1/admin/*` only, `sysadmin` (`/api/v1/whoami` accepts any valid token).
- **Synchronous business actions.** The API changes state inside one
  PostgreSQL transaction and writes an outbox row in the same transaction.
  Business routes never call Flowable: the worker drives every process,
  outside any database transaction. The sysadmin endpoints only read Flowable
  and retry dead-letter jobs, so a Flowable outage never blocks the kitchen.
- **Workflow scope.** Flowable runs only processes that need timers and human
  steps: incident recall and cold-chain alerts. The kitchen flow is a state
  machine in the API.

## Identity model

- Realm roles (internal): `qa`, `procurement`, `chef`, `driver`, `cskh`,
  `director`, `approver`. Customer role: `customer_staff`. Machine: `sensor`.
  Platform: `sysadmin` (core admin only, sees no business data).
- Customers are Keycloak **Organizations** keyed by alias (`truong-a`,
  `truong-b`, `truong-c`, `nha-may-x`). Tokens carry an `organization` claim
  when the client requests `scope=openid organization`.
- Clients: `clew-web` (public, PKCE), `clew-cli` (public, device flow),
  `sensor-gateway` (client credentials), `clew-api` (audience). The client
  `clew-test` (direct access grants) exists only when the `test` overlay is
  applied, never in a demo.

## Admin plane (tier 1)

System admins manage the headless core without touching business data.
Everything here is bound to `127.0.0.1`. The gateway has a second listener
(`:9081`) for the admin plane; every route belongs to exactly one listener:

| Service | Admin UI | Where |
|---|---|---|
| Keycloak (SSO) | Keycloak admin console of realm `clew` (users, roles, organizations, sessions, events); the master realm is not routed | `http://localhost:9081/auth/admin/clew/console/` |
| SeaweedFS (files) | Master UI (cluster, volumes), filer UI (browse stored files); no login, so closed by default (`make admin-tools-open`) | `http://localhost:9333/`, `http://localhost:8888/` |
| All core services | Clew core admin: health of every service, Flowable processes, tasks, timers and dead-letter retry, outbox, gateway routes | `http://localhost:9080/admin` (role `sysadmin`) |

Flowable 8 and APISIX in standalone mode ship no open source admin UI, so the
core admin page covers them through their own APIs (Flowable REST, APISIX
Control API on the internal network). Details: [admin-guide.md](admin-guide.md).

## Time

The database stores `timestamptz` in UTC. Business dates (service day, meal
time) are computed in `BUSINESS_TZ=Asia/Ho_Chi_Minh`. The API returns
`server_now` so countdowns in the UI do not depend on the client clock.

## Machines and evidence

- **Sensors** use their own machine identity (`sensor-gateway`, client
  credentials) with a claim listing the assets they may report for, through a
  separate gateway route with its own rate-limit bucket.
- **Audit chain:** every business change appends a hash-chained audit event in
  the same transaction. The chain head (seq, hash) is printed outside the
  database (recall notices, PDF footers, drill results) and can be verified
  against it later. This is tamper-evidence, not a digital signature.

## Tier boundary

Tier 2 reaches PostgreSQL, SeaweedFS and Flowable directly on the internal
docker network (PostgreSQL cannot sit behind an HTTP gateway). If all Tier 1
access had to go through the gateway, Flowable and S3 traffic would move to
internal APISIX routes with a service token.
