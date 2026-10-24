"""One-command demo: python demo.py
Starts a local web page that "releases" on the 3rd request, and polls it 5 times.
"""
import http.server
import json
import os
import sys
import tempfile
import threading

os.environ["POLLERS_STATE"] = os.path.join(tempfile.mkdtemp(prefix="pollers-demo-"), "state.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pollers import core  # noqa: E402

hits = {"n": 0}


class Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        hits["n"] += 1
        body = b"<h1>Release notes</h1>Version 2 is out" if hits["n"] >= 3 else b"<h1>Release notes</h1>Version 1"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Page)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d/" % srv.server_port
pollers = [{"name": "docs-v2", "url": url, "kind": "contains", "pattern": "Version 2", "subject": "Docs v2 is live"}]

for i in range(1, 6):
    fired = core.run_once(pollers, dry_run=True)
    st = core.load_state()["docs-v2"]
    print("pass %d: page requests=%d  fired=%s  finished=%s" % (i, hits["n"], fired or "-", st.get("finished", False)))
print("Pass 4 and 5 made no request: a finished poller never runs again.")
srv.shutdown()
