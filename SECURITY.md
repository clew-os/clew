<!--
SPDX-FileCopyrightText: The Clew Authors
SPDX-License-Identifier: Apache-2.0
-->

# Security policy

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's
"Report a vulnerability" (private security advisory) on this repository.
We aim to answer within 7 days.

## Scope and design notes

- Clew is a demo-grade system meant to run on a single machine. All ports
  are bound to `127.0.0.1`. The gateway has two listeners: `:9080` (public
  plane, answers 404 for `/auth/admin/*`) and `:9081` (admin plane: only the
  Keycloak admin console of realm `clew`; the master realm is not routed).
  The SeaweedFS UIs have no login and are closed unless an admin opens them
  for maintenance (`make admin-tools-open`). Never publish either plane beyond
  the loopback interface.
- App tokens (`clew-web`, `clew-cli`) map only app roles (full scope off), so
  they never carry Keycloak admin roles. The sysadmin's console grants exclude
  impersonation and client secrets; Keycloak keeps login and admin events.
  The test overlay (`make dev-ports`) also publishes PostgreSQL, Keycloak and
  Flowable on `127.0.0.1`.
- The `sysadmin` role reaches only `/api/v1/admin/*` and no business data;
  business roles cannot reach the admin endpoints. Admin actions (dead-letter
  and outbox retries) are written to the audit chain.
- Secrets live only in `.env`, generated per installation by `make init`.
- The API re-verifies every JWT (signature via JWKS, issuer, audience, expiry)
  behind the gateway and denies by default.
- The audit log is a hash chain: tamper-evident, not a digital signature. The
  runtime database role cannot update, delete or truncate audit rows.
