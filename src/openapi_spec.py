"""OpenAPI 3.0 spec for mta.shubhthorat.com"""

from __future__ import annotations


def build_openapi_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MTA BusTime API",
            "version": "1.0.0",
            "description": (
                "Real-time MTA bus data via bustime.mta.info.\n\n"
                "Get live arrivals at any stop, track all vehicles on a route, "
                "and browse all stops for any bus line — no API key required.\n\n"
                "No authentication required."
            ),
        },
        "servers": [{"url": "https://mta.shubhthorat.com"}],
        "paths": {
            "/api/health": {
                "get": {
                    "summary": "Health check",
                    "operationId": "health",
                    "tags": ["Meta"],
                    "responses": {
                        "200": {"description": "Service is up", "content": {"application/json": {"example": {"status": "ok", "service": "mta"}}}},
                    },
                }
            },
            "/api/mta/arrivals": {
                "get": {
                    "summary": "Real-time arrivals at a stop",
                    "description": "Returns upcoming buses with distance, stops away, and presentable ETA.",
                    "operationId": "mtaArrivals",
                    "tags": ["MTA"],
                    "parameters": [
                        {"name": "stop", "in": "query", "required": True, "schema": {"type": "string"}, "description": "MTA stop id (6-digit, e.g. 400001)"},
                        {"name": "line", "in": "query", "schema": {"type": "string"}, "description": "Optional route filter (e.g. M15, Q32)"},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}},
                        {"name": "timeout", "in": "query", "schema": {"type": "integer", "minimum": 5, "maximum": 120}},
                    ],
                    "responses": {"200": {"description": "Arrivals list with distance and ETA info"}},
                }
            },
            "/api/mta/vehicles": {
                "get": {
                    "summary": "Active vehicles on a route",
                    "description": "Returns all buses currently running on a route with GPS location and next stop.",
                    "operationId": "mtaVehicles",
                    "tags": ["MTA"],
                    "parameters": [
                        {"name": "line", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Route name (e.g. M15, Q32, B44, Bx12)"},
                        {"name": "timeout", "in": "query", "schema": {"type": "integer", "minimum": 5, "maximum": 120}},
                    ],
                    "responses": {"200": {"description": "Vehicle positions and status"}},
                }
            },
            "/api/mta/route/stops": {
                "get": {
                    "summary": "All stops on a route",
                    "description": "Returns all stops in order with stop ids, names, and coordinates.",
                    "operationId": "mtaRouteStops",
                    "tags": ["MTA"],
                    "parameters": [
                        {"name": "line", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Route name (e.g. M15, Q32, B44, Bx12)"},
                        {"name": "timeout", "in": "query", "schema": {"type": "integer", "minimum": 5, "maximum": 120}},
                    ],
                    "responses": {"200": {"description": "Ordered stop list with ids and coordinates"}},
                }
            },
        },
        "tags": [
            {"name": "MTA", "description": "Real-time bus data via bustime.mta.info"},
            {"name": "Meta", "description": "Service health"},
        ],
    }
