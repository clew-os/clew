# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""The gateway view exposes plugin names and upstream nodes, never plugin configuration."""

from app.services.admin_gateway import sanitize_routes, sanitize_upstreams

CONTROL_API_ROUTES = [
    {
        "key": "/routes/api",
        "value": {
            "id": "api",
            "uri": "/api/*",
            "priority": 5,
            "upstream_id": "api",
            "plugins": {
                "openid-connect": {"client_id": "clew-api", "client_secret": "SUPER-SECRET-VALUE", "discovery": "x"},
                "limit-req": {"rate": 50},
            },
        },
    },
    {"value": {"id": "auth", "uris": ["/auth/a/*", "/auth/b"], "priority": 10, "upstream_id": "keycloak"}},
    {"value": {"no": "id"}},
]
CONTROL_API_UPSTREAMS = [
    {"value": {"id": "keycloak", "nodes": [{"host": "keycloak", "port": 8080, "weight": 1}], "secret": "S3"}},
    {"value": {"id": "legacy", "nodes": {"web:80": 1}}},
]


def test_routes_keep_names_only_and_never_secret_values():
    routes = sanitize_routes(CONTROL_API_ROUTES)
    dumped = " ".join(r.model_dump_json() for r in routes)
    assert "SUPER-SECRET-VALUE" not in dumped and "client_secret" not in dumped and "clew-api" not in dumped
    assert [r.id for r in routes] == ["auth", "api"]  # priority desc
    api = routes[1]
    assert api.uris == ["/api/*"] and api.plugins == ["limit-req", "openid-connect"] and api.upstream_id == "api"
    assert routes[0].uris == ["/auth/a/*", "/auth/b"] and routes[0].plugins == []


def test_upstreams_list_host_port_only():
    upstreams = sanitize_upstreams(CONTROL_API_UPSTREAMS)
    assert [(u.id, u.nodes) for u in upstreams] == [("keycloak", ["keycloak:8080"]), ("legacy", ["web:80"])]
    assert "S3" not in " ".join(u.model_dump_json() for u in upstreams)


def test_garbage_payloads_yield_empty_lists():
    assert sanitize_routes({"unexpected": 1}) == [] and sanitize_upstreams(None) == []
