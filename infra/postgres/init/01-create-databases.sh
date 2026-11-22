#!/usr/bin/env bash
# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
#
# Runs once on an empty data volume. Creates one database per core service.
# clew uses two roles: clew_migrator (schema owner, runs alembic) and
# clew_app (runtime; cannot UPDATE/DELETE audit_event, see migrations).
# Passwords are passed as psql variables (:'var'), never pasted into SQL text.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v kc_pw="$KC_DB_PASSWORD" -v fl_pw="$FLOWABLE_DB_PASSWORD" \
  -v mig_pw="$CLEW_MIGRATOR_PASSWORD" -v app_pw="$CLEW_APP_PASSWORD" <<-'SQL'
  CREATE ROLE keycloak LOGIN PASSWORD :'kc_pw';
  CREATE DATABASE keycloak OWNER keycloak;

  CREATE ROLE flowable LOGIN PASSWORD :'fl_pw';
  CREATE DATABASE flowable OWNER flowable;

  CREATE ROLE clew_migrator LOGIN PASSWORD :'mig_pw';
  CREATE ROLE clew_app LOGIN PASSWORD :'app_pw';
  CREATE DATABASE clew OWNER clew_migrator;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname clew <<-'SQL'
  REVOKE ALL ON SCHEMA public FROM PUBLIC;
  GRANT USAGE ON SCHEMA public TO clew_app;
  ALTER SCHEMA public OWNER TO clew_migrator;
SQL
