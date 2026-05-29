"""Standalone MTA BusTime API — WSGI entry point for Vercel."""

from __future__ import annotations

import json
import os

from .mta.routes import dispatch_mta
from .mcp import handle_mcp
from .openapi_spec import build_openapi_spec

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_SCALAR_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" type="image/png" href="/favicon.png" />
    <title>MTA BusTime API</title>
  </head>
  <body>
    <script id="api-reference" data-url="/openapi.json"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>"""


def _json(start_response, status: str, body: dict):
    data = json.dumps(body).encode()
    start_response(status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(data))),
        ("Access-Control-Allow-Origin", "*"),
    ])
    return [data]


def _html(start_response, html: str):
    raw = html.encode("utf-8")
    start_response("200 OK", [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(raw))),
        ("Cache-Control", "no-store"),
    ])
    return [raw]


def _static(start_response, filepath: str, content_type: str):
    with open(filepath, "rb") as f:
        data = f.read()
    start_response("200 OK", [
        ("Content-Type", content_type),
        ("Content-Length", str(len(data))),
        ("Cache-Control", "public, max-age=86400"),
    ])
    return [data]


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/favicon.png":
        return _static(start_response, os.path.join(_STATIC_DIR, "favicon.png"), "image/png")

    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Content-Length", "0"),
        ])
        return [b""]

    if method == "POST" and path in ("/", "/mcp"):
        try:
            body_len = int(environ.get("CONTENT_LENGTH") or 0)
            body_bytes = environ["wsgi.input"].read(body_len) if body_len else b""
        except Exception:
            body_bytes = b""
        status_code, response = handle_mcp(body_bytes)
        if response is None:
            start_response("202 Accepted", [("Content-Length", "0"), ("Access-Control-Allow-Origin", "*")])
            return [b""]
        data = json.dumps(response).encode()
        start_response(f"{status_code} OK", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(data))),
            ("Access-Control-Allow-Origin", "*"),
        ])
        return [data]

    if method == "GET" and path in ("/", "/docs"):
        return _html(start_response, _SCALAR_HTML)

    if method == "GET" and path == "/openapi.json":
        return _json(start_response, "200 OK", build_openapi_spec())

    if method == "GET" and path == "/api/health":
        return _json(start_response, "200 OK", {"status": "ok", "service": "mta"})

    if path.startswith("/api/mta"):
        status, body = dispatch_mta(method, path, environ)
        return _json(start_response, status, body)

    return _json(start_response, "404 Not Found", {"error": "not found"})
