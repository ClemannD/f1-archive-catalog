#!/usr/bin/env python3
"""
Local ingest server for F1TV archive scraper.

- POST /add       — accepts JSON array of scraped entries, merges into regions/us.json
- GET  /current   — returns current catalog contents
- GET  /script    — returns the Tampermonkey userscript
- GET  /           — status page
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from catalog_utils import load_races, merge_entries

CATALOG_PATH = os.path.join(REPO_ROOT, "regions", "us.json")
USERSCRIPT_PATH = os.path.join(os.path.dirname(__file__), "f1tv-scraper.user.js")
RACES_BY_SEASON = load_races()

def load_catalog():
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)

def save_catalog(data):
    data.sort(key=lambda e: (e["season"], e.get("round") or 9999, e.get("type", ""), e["name"]))
    with open(CATALOG_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

TYPE_MAP = {
    "replay": "race",
    "race": "race",
    "extended highlights": "extended_highlights",
    "highlights": "highlights",
    "season review": "season_review",
    "season recap": "season_review",
}

def normalize_type(raw):
    return TYPE_MAP.get(raw.strip().lower(), raw.strip().lower())


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/current":
            data = load_catalog()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())

        elif self.path == "/script":
            with open(USERSCRIPT_PATH, "r") as f:
                script = f.read()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(script.encode())

        else:
            catalog = load_catalog()
            seasons = {}
            for e in catalog:
                seasons.setdefault(e["season"], []).append(e)
            season_summary = ", ".join(
                f"{s}: {len(entries)}" for s, entries in sorted(seasons.items())
            )
            html = f"""<html><body style="font-family:monospace;background:#1a1a2e;color:#eee;padding:2em">
<h1>F1 Archive Catalog Server</h1>
<p><b>Catalog:</b> {len(catalog)} entries</p>
<p><b>Seasons:</b> {season_summary or "none yet"}</p>
<hr>
<p>Install <code>f1tv-scraper.user.js</code> in Tampermonkey, then scrape pages on f1tv.formula1.com.</p>
<p>See <code>scraper/README.md</code> in this repo for setup.</p>
<hr>
<p><a href="/current" style="color:cyan">GET /current</a> — raw JSON</p>
<p><a href="/script" style="color:cyan">GET /script</a> — userscript file</p>
</body></html>"""
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

    def do_POST(self):
        if self.path == "/add":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                new_entries = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return

            for e in new_entries:
                e["type"] = normalize_type(e.get("type", "race"))

            catalog = load_catalog()
            catalog, added, updated = merge_entries(catalog, new_entries, RACES_BY_SEASON)
            save_catalog(catalog)

            resp = {
                "message": f"Done! Added {added}, updated {updated}.",
                "added": added,
                "updated": updated,
                "total": len(catalog),
            }
            print(f"  → Added {added}, updated {updated}, total {len(catalog)}")

            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[server] {args[0]}")


if __name__ == "__main__":
    port = 8484
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"F1 Archive Catalog Server running at http://localhost:{port}")
    print(f"   Status page:  http://localhost:{port}/")
    print(f"   Userscript:   http://localhost:{port}/script")
    print(f"   Catalog JSON: http://localhost:{port}/current")
    print(f"   Writing to:   {CATALOG_PATH}")
    print()
    print("Use the Tampermonkey userscript on F1TV archive pages.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
