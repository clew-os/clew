<!--
SPDX-FileCopyrightText: The Clew Authors
SPDX-License-Identifier: Apache-2.0
-->

# Administering the headless core (tier 1)

Tier 1 has no screens for end users, but system admins need to see and manage
it. This guide covers who the admin is, where each admin UI lives and the
everyday tasks. Nothing here depends on the catering domain: the same admin
plane would serve any tier-2 application built on this core.

## Two planes

| Plane | Bound to | What | Who |
|---|---|---|---|
| Public | `127.0.0.1:9080` (APISIX listener 1) | SPA, `/api/*`, `/auth/*` allowlist | Staff, customers, machines, and the `/admin` page |
| Admin | `127.0.0.1:9081` (APISIX listener 2) | Keycloak admin console of realm `clew` only | System admin on the server machine |
| Maintenance | `127.0.0.1:9333`, `:8888`, closed by default | SeaweedFS master and filer UIs | System admin, for a maintenance window |

Every gateway route is bound to one listener. On `:9080`, `/auth/admin/*`
answers 404. On `:9081`, only the console of realm `clew`, its admin REST calls
and static resources are routed; the master realm, other realms, the API and
the web app answer 404. Everything is published on the loopback interface only.
On a real server, reach it through an SSH tunnel, never by publishing it.

## Account

`sysadmin-khoa` (password: `DEMO_USER_PASSWORD` in `.env`) has two grants:

- realm role `sysadmin`: the Clew core admin page and `/api/v1/admin/*` only.
  It is not a business role, so every business screen and endpoint answers 403;
- a least-privilege set of `realm-management` roles of realm `clew` (view and
  manage the realm, users and organizations; view clients and events): the
  Keycloak admin console of that realm, with the same login (single sign-on).
  No `impersonation` (so the admin cannot act as QA or the approver) and no
  access to client secrets.

Those console grants never travel in app tokens: `clew-web` and `clew-cli`
have full scope off and map only the app roles, so a token taken from the web
app is not a Keycloak admin credential. Keycloak records login and admin events
(30 days), visible in the console under Events.

The Keycloak bootstrap admin (`admin` in the master realm, `KC_ADMIN_PASSWORD`)
is used by the one-shot `kc-bootstrap` over the internal network only. The
master realm has no route on either plane. Break-glass access:
`docker compose exec keycloak /opt/keycloak/bin/kcadm.sh`.

## Where each service is administered

| Service | Admin UI | Typical tasks |
|---|---|---|
| All | <http://localhost:9080/admin> (Clew core admin) | Health, version and latency of every core service, refreshed every 10 s; links to the native consoles |
| Keycloak (SSO) | <http://localhost:9081/auth/admin/clew/console/> | Add a staff account and give it a role; add a customer organization and its members; reset a password; end sessions |
| APISIX (gateway) | `/admin/gateway` (read-only) | See routes, their plugins and upstreams. Routes are code: edit `infra/apisix/apisix.yaml`, then `docker compose restart apisix` |
| PostgreSQL | `/admin` (version, size) and `psql` | Backup and restore (below) |
| SeaweedFS (files) | `/admin` (cluster leader, bucket reachable); for maintenance `make admin-tools-open` → <http://localhost:9333/> master, <http://localhost:8888/> filer, then `make admin-tools-close` | Cluster and volume state; browse stored objects. Users only ever download files through the API |
| Flowable (workflow) | `/admin/workflow` | Process definitions, running instances, open tasks, timers; move a dead-letter job back to the queue |
| Outbox (platform) | `/admin/outbox` | Backlog and failures between the API and the worker; retry a failed event |

Why some services have no native console: Flowable 8 ships no open source admin
UI, and APISIX runs in standalone mode (routes from a file, no Admin API, no
dashboard) so the running gateway cannot drift from the repository. The core
admin page covers both through their own APIs: Flowable REST, and the APISIX
Control API, which is reachable on the internal docker network only and is
read without plugin configuration (no secrets leave the API).

## Everyday tasks

**Is everything up?** Open `/admin`. Each card shows up, degraded or down, the
latency and a few facts. The outbox turns "degraded" when an event failed or
the oldest pending event is older than two minutes, which usually means the
worker or Flowable is down.

**A recall process is stuck.** `/admin/workflow` lists dead-letter jobs with
their error. Fix the cause, then "Thử lại" (retry) moves the job back to the
queue. Every retry is written to the audit chain with the admin's name.

**An outbox event failed.** `/admin/outbox` shows failed events and their last
error. Retry puts the event back for the worker; it is also audited. Handlers
are idempotent, so a retry never starts a second process for the same incident.

**A new school becomes a customer.** In the Keycloak console: Organizations →
Create (alias, e.g. `truong-d`) → Members → add the school's staff accounts,
each with the realm role `customer_staff`. The portal scopes data by that alias.

**Backup and restore (demo scale).**

```bash
docker compose exec -T postgres pg_dumpall -U postgres > clew-backup.sql
docker compose exec -T postgres psql -U postgres < clew-backup.sql   # into a fresh stack
```

SeaweedFS data lives in the `clew_seaweed` volume; back it up with the
volume (stop the stack first). `make reset` deletes all volumes and returns to
the realm and data in the repository.

## Security notes

- The SeaweedFS UIs have no login, and the master API changes state on plain
  GET requests (a web page could trigger them). They are closed by default;
  open them only for a maintenance window and close them again.
- Changes made in the Keycloak console live in the `keycloak` database. The
  realm file in the repository is only imported on the first start.
- The `sysadmin` endpoints use the same zero-trust path as everything else:
  JWT checked at the gateway and again in the API, role checked per route.
