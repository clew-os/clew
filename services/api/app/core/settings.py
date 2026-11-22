# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Runtime settings, read from environment variables (see compose.yaml)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_ignore_empty=True)

    # OIDC: tokens carry the PUBLIC issuer (browser origin), while keys are
    # fetched over the internal docker network.
    oidc_issuer: str = "http://localhost:9080/auth/realms/clew"
    oidc_jwks_url: str = "http://keycloak:8080/auth/realms/clew/protocol/openid-connect/certs"
    oidc_audience: str = "clew-api"
    oidc_leeway_seconds: int = 30

    # Runtime role (clew_app) cannot UPDATE/DELETE the audit chain.
    database_url: str = "postgresql+psycopg://clew_app:clew_app@localhost:5432/clew"

    # Object storage (SeaweedFS S3). Files are always streamed through the API.
    s3_endpoint_url: str = "http://seaweedfs:8333"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "clew-files"
    upload_max_bytes: int = 10 * 1024 * 1024

    # Workflow engine. Business routes never call it (they emit outbox events); only the
    # worker and the sysadmin endpoints under /api/v1/admin (short timeouts) do.
    flowable_url: str = "http://flowable:8080/flowable-rest"
    flowable_user: str = "rest-admin"
    flowable_password: str = ""

    # Tier-1 admin probes (/api/v1/admin): docker-network defaults, so compose needs no extra variables.
    keycloak_internal_url: str = "http://keycloak:8080/auth"
    keycloak_management_url: str = "http://keycloak:9000/auth"
    keycloak_realm: str = "clew"
    apisix_control_url: str = "http://apisix:9090"
    seaweedfs_master_url: str = "http://seaweedfs:9333"
    admin_probe_timeout_s: float = 3.0
    # Native admin consoles, opened by the sysadmin in a browser ON the server machine (loopback only).
    keycloak_console_url: str = "http://localhost:9081/auth/admin/clew/console/"
    seaweedfs_console_url: str = "http://localhost:9333/"
    seaweedfs_filer_console_url: str = "http://localhost:8888/"

    # Incident triage SLA before the director is pulled in (ISO 8601; demo uses PT1M).
    incident_triage_sla: str = "PT30M"
    # Cold-chain alert: time for QA to check the fridge before the director is pulled in.
    coldchain_check_sla: str = "PT10M"

    # Recall notices cover deliveries of the last N service days (older food is long eaten).
    recall_window_days: int = Field(3, ge=0, le=30)

    # P6 complaint SLA comes from the customer profile (sla_hours); demos can shorten it.
    complaint_sla_override_minutes: int | None = None

    # Local LLM for report DRAFTS (Ollama on the host). Missing/slow => deterministic template.
    llm_base_url: str = "http://host.docker.internal:11434"
    llm_model: str = "qwen3:4b"
    llm_timeout_s: float = 30.0

    # Business time zone: DB stores UTC, service dates are computed here.
    business_tz: str = "Asia/Ho_Chi_Minh"


@lru_cache
def get_settings() -> Settings:
    return Settings()
