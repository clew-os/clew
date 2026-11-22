# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""APISIX Control API -> a view that is safe to show: route ids, URIs, plugin NAMES and upstream
nodes. The raw payload carries full plugin configuration (client secrets); none of it is copied."""

from typing import Any

import httpx

from app.core.errors import InfraError
from app.core.settings import get_settings
from app.schemas.admin import GatewayOverviewOut, GatewayRouteOut, GatewayUpstreamOut


def _value(item: Any) -> dict[str, Any]:
    """Control API entries are {"key":..., "value": {...}}; accept a bare object too."""
    if isinstance(item, dict):
        inner = item.get("value")
        return inner if isinstance(inner, dict) else item
    return {}


def sanitize_routes(raw: Any) -> list[GatewayRouteOut]:
    routes = []
    for item in raw if isinstance(raw, list) else []:
        route = _value(item)
        if not route.get("id"):
            continue
        uris = route.get("uris") or ([route["uri"]] if route.get("uri") else [])
        plugins = route.get("plugins")
        routes.append(
            GatewayRouteOut(
                id=str(route["id"]),
                uris=[str(u) for u in uris],
                priority=int(route.get("priority") or 0),
                upstream_id=str(route["upstream_id"]) if route.get("upstream_id") else None,
                plugins=sorted(str(name) for name in plugins) if isinstance(plugins, dict) else [],
            )
        )
    return sorted(routes, key=lambda r: (-r.priority, r.id))


def sanitize_upstreams(raw: Any) -> list[GatewayUpstreamOut]:
    upstreams = []
    for item in raw if isinstance(raw, list) else []:
        upstream = _value(item)
        if not upstream.get("id"):
            continue
        nodes = upstream.get("nodes")
        if isinstance(nodes, dict):  # APISIX also accepts {"host:port": weight}
            hosts = [str(k) for k in nodes]
        elif isinstance(nodes, list):
            hosts = [f"{n.get('host')}:{n.get('port')}" for n in nodes if isinstance(n, dict)]
        else:
            hosts = []
        upstreams.append(GatewayUpstreamOut(id=str(upstream["id"]), nodes=hosts))
    return sorted(upstreams, key=lambda u: u.id)


def _get(path: str) -> Any:
    settings = get_settings()
    try:
        res = httpx.get(f"{settings.apisix_control_url.rstrip('/')}{path}", timeout=settings.admin_probe_timeout_s)
        res.raise_for_status()
        return res.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise InfraError(f"apisix control api {path}: {type(exc).__name__}") from exc


def gateway_overview() -> GatewayOverviewOut:
    """Raises InfraError when the control API is unreachable."""
    return GatewayOverviewOut(
        routes=sanitize_routes(_get("/v1/routes")), upstreams=sanitize_upstreams(_get("/v1/upstreams"))
    )
