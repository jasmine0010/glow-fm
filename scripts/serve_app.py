"""Serve app/ locally, telling the browser to check for a newer copy of every file on each load.

    python scripts/serve_app.py            # http://127.0.0.1:8765
    python scripts/serve_app.py 9000       # another port

Python's plain http.server sends no caching instructions, so browsers guess and can keep an old script or data file
while the page around it is new. This sends "Cache-Control: no-cache": the browser may keep a copy, but asks first.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


class Server(ThreadingHTTPServer):
    # The story page asks for a few dozen files at once. Python's default queue holds 5 waiting connections, and on
    # Windows the rest are refused, which the browser reports as "Failed to fetch".
    request_queue_size = 128
    daemon_threads = True


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = Server(("127.0.0.1", port), partial(NoCache, directory=str(APP)))
    print(f"Serving {APP} at http://127.0.0.1:{port}")
    server.serve_forever()
