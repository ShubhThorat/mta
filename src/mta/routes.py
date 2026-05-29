"""WSGI helpers: MTA BusTime as ``/api/mta/*`` (real-time, read-only)."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

from .sdk import fetch_arrivals, fetch_vehicles, fetch_route_stops


def _parse_qs(environ) -> dict[str, list[str]]:
    return parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=False)


def _first(qs: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    v = qs.get(key)
    if not v:
        return default
    return v[0] if v[0] else default


def _int(qs: dict[str, list[str]], key: str, default: int, *, min_v: int = 1, max_v: int = 120) -> int:
    raw = _first(qs, key)
    if raw is None:
        return default
    try:
        n = int(raw)
    except ValueError:
        return default
    return max(min_v, min(max_v, n))


def _timeout(qs: dict[str, list[str]]) -> int:
    return _int(qs, "timeout", 30, min_v=5, max_v=120)


def dispatch_mta(method: str, path: str, environ) -> tuple[str, dict]:
    """Handle any path under ``/api/mta``. Returns (HTTP status line, JSON body dict)."""
    rest = path[len("/api/mta"):].strip("/")
    parts = [p for p in rest.split("/") if p]
    qs = _parse_qs(environ)
    timeout = _timeout(qs)

    if method != "GET":
        return ("405 Method Not Allowed", {"error": "only GET is supported for /api/mta"})

    if not parts:
        return (
            "400 Bad Request",
            {
                "error": "missing subpath",
                "hint": "try /api/mta/arrivals?stop=400001, /api/mta/vehicles?line=M15, /api/mta/route/stops?line=M15",
            },
        )

    try:
        # /api/mta/arrivals?stop=400001[&line=M15][&limit=10]
        if parts[0] == "arrivals":
            stop_id = _first(qs, "stop") or ""
            if not stop_id:
                return (
                    "400 Bad Request",
                    {"error": "pass stop= (stop id)", "example": "/api/mta/arrivals?stop=400001"},
                )
            line = _first(qs, "line") or None
            limit = _int(qs, "limit", 10, min_v=1, max_v=50)
            data = fetch_arrivals(stop_id, line=line, limit=limit, timeout=timeout)
            return ("200 OK", {"data": data})

        # /api/mta/vehicles?line=M15
        if parts[0] == "vehicles":
            line = _first(qs, "line") or ""
            if not line:
                return (
                    "400 Bad Request",
                    {"error": "pass line= (route, e.g. M15)", "example": "/api/mta/vehicles?line=M15"},
                )
            data = fetch_vehicles(line, timeout=timeout)
            return ("200 OK", {"data": data})

        # /api/mta/route/stops?line=M15
        if parts[0] == "route" and len(parts) == 2 and parts[1] == "stops":
            line = _first(qs, "line") or ""
            if not line:
                return (
                    "400 Bad Request",
                    {"error": "pass line= (route, e.g. M15)", "example": "/api/mta/route/stops?line=M15"},
                )
            data = fetch_route_stops(line, timeout=timeout)
            return ("200 OK", {"data": data})

    except HTTPError as e:
        return ("502 Bad Gateway", {"error": "MTA API error", "upstream_status": e.code, "reason": e.reason})
    except URLError as e:
        return ("502 Bad Gateway", {"error": "MTA network error", "reason": str(e.reason)})
    except (ValueError, json.JSONDecodeError) as e:
        return ("502 Bad Gateway", {"error": "MTA response parse error", "detail": str(e)})

    return ("404 Not Found", {"error": "unknown /api/mta path"})
