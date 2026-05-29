"""MCP Streamable HTTP transport (2025-03-26) for the MTA BusTime API."""

from __future__ import annotations

import json
from io import BytesIO
from urllib.parse import urlencode

from .mta.routes import dispatch_mta

PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "mta"
SERVER_VERSION = "1.0.0"

TOOLS = [
    {
        "name": "arrivals",
        "description": (
            "Real-time bus arrivals at an MTA stop. "
            "Returns upcoming buses with distance, stops away, and presentable ETA. "
            "Optionally filter by route (e.g. M15, Q32, B44)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "stop": {
                    "type": "string",
                    "description": "MTA stop id (6-digit number, e.g. 400001). Use route_stops to find stop ids.",
                },
                "line": {
                    "type": "string",
                    "description": "Optional route filter, e.g. M15, Q32, B44-SBS",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Max arrivals to return (default 10)",
                },
                "timeout": {"type": "integer", "minimum": 5, "maximum": 120},
            },
            "required": ["stop"],
        },
    },
    {
        "name": "vehicles",
        "description": (
            "All active buses on an MTA route right now. "
            "Returns each vehicle's GPS location, bearing, next stop, and progress status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "line": {
                    "type": "string",
                    "description": "Route name, e.g. M15, Q32, B44, Bx12",
                },
                "timeout": {"type": "integer", "minimum": 5, "maximum": 120},
            },
            "required": ["line"],
        },
    },
    {
        "name": "route_stops",
        "description": (
            "All stops on an MTA bus route in order, with stop ids, names, and coordinates. "
            "Use this to discover stop ids for the arrivals tool."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "line": {
                    "type": "string",
                    "description": "Route name, e.g. M15, Q32, B44, Bx12",
                },
                "timeout": {"type": "integer", "minimum": 5, "maximum": 120},
            },
            "required": ["line"],
        },
    },
]


def _call_tool(name: str, args: dict) -> dict:
    timeout = args.get("timeout", 30)

    if name == "arrivals":
        path = "/api/mta/arrivals"
        params: dict = {"stop": args.get("stop", ""), "timeout": timeout}
        if args.get("line"):
            params["line"] = args["line"]
        if args.get("limit"):
            params["limit"] = args["limit"]
        qs = urlencode(params)
    elif name == "vehicles":
        path = "/api/mta/vehicles"
        qs = urlencode({"line": args.get("line", ""), "timeout": timeout})
    elif name == "route_stops":
        path = "/api/mta/route/stops"
        qs = urlencode({"line": args.get("line", ""), "timeout": timeout})
    else:
        return {"error": f"unknown tool: {name}"}

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": qs,
        "wsgi.input": BytesIO(b""),
    }
    _status, body = dispatch_mta("GET", path, environ)
    return body


def handle_mcp(body_bytes: bytes) -> tuple[int, dict | None]:
    """Process a JSON-RPC MCP request. Returns (http_status, body_or_None)."""
    try:
        msg = json.loads(body_bytes)
    except (json.JSONDecodeError, ValueError):
        return (400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

    msg_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params") or {}

    if msg_id is None:
        return (202, None)

    if method == "initialize":
        return (200, {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        })

    if method == "ping":
        return (200, {"jsonrpc": "2.0", "id": msg_id, "result": {}})

    if method == "tools/list":
        return (200, {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}
        result = _call_tool(tool_name, arguments)
        return (200, {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]},
        })

    return (200, {
        "jsonrpc": "2.0", "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    })
