"""Local dev server — python main.py"""

from __future__ import annotations

import sys
from wsgiref.simple_server import make_server

sys.path.insert(0, "src")

from src.index import app  # noqa: E402

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    with make_server("", port, app) as httpd:
        print(f"Serving on http://localhost:{port}")
        httpd.serve_forever()
