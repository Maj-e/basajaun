"""Serve web/ locally without browser caching (make serve).

The page is made of ES modules: with Python's plain http.server the browser may keep
some modules from an earlier version and fetch others fresh, and a mix of versions
stops the page before anything is drawn. `no-store` makes every reload consistent.
"""
from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("", port), partial(NoCacheHandler, directory=str(WEB)))
    print(f"Serving web/ at http://localhost:{port} (no browser cache)")
    server.serve_forever()


if __name__ == "__main__":
    main()
