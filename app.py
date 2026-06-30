"""Confidential user-data store — the API in front of an in-enclave PostgreSQL.

A B2C product stores its users' records here. Postgres keeps its data on the
per-app sealed /data volume, so the records are encrypted at rest under a key
only the app owner controls — the host, the operator, and Privasys never see the
plaintext. The endpoint is attestable end to end (RA-TLS), and the data survives
platform/app upgrades only after the owner approves the new code.

Tools (declared in privasys.json; callable from agents / the portal):
  create_user  POST {"name","email"}   -> {"id", ...}
  get_user     POST {"id"}             -> the record
  list_users   POST {}                 -> all records

Plain HTTP:
  GET /health  -> liveness (the manager probes localhost:$PORT/health)
"""

import http.server
import json
import os
import time
from urllib.parse import urlparse

import psycopg2

# The platform injects a unique $PORT per app; the API listens on it.
# $PORT is required — no hard-coded fallback (for a local run, set it).
_port = os.environ.get("PORT")
if not _port:
    raise SystemExit("PORT environment variable is required")
PORT = int(_port)
DSN = "host=127.0.0.1 port=5432 dbname=appdb user=postgres"


def connect(retries: int = 30):
    """Connect to the local Postgres, retrying while it finishes starting."""
    last = None
    for _ in range(retries):
        try:
            return psycopg2.connect(DSN)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1)
    raise last


def init_schema() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id SERIAL PRIMARY KEY, "
            "name TEXT NOT NULL, "
            "email TEXT NOT NULL, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conn.commit()


class Handler(http.server.BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _payload(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}"), None
        except json.JSONDecodeError:
            return None, "invalid JSON body"

    # ── GET ──────────────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            try:
                with connect(retries=1) as conn, conn.cursor() as cur:
                    cur.execute("SELECT 1")
                self._json(200, {"status": "healthy"})
            except Exception:  # noqa: BLE001
                self._json(503, {"status": "starting"})
        elif path == "/":
            self._json(200, {"status": "ok", "service": "confidential-user-store"})
        else:
            self._json(404, {"error": "not found"})

    # ── POST ─────────────────────────────────────────────────────────
    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/create_user", "/users"):
            self._create_user()
        elif path == "/get_user":
            self._get_user()
        elif path == "/list_users":
            self._list_users()
        else:
            self._json(404, {"error": "not found"})

    def _create_user(self) -> None:
        body, err = self._payload()
        if err:
            self._json(400, {"error": err})
            return
        name, email = body.get("name"), body.get("email")
        if not isinstance(name, str) or not name or not isinstance(email, str) or not email:
            self._json(400, {"error": "name and email (non-empty strings) are required"})
            return
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id, created_at",
                (name, email),
            )
            uid, created = cur.fetchone()
            conn.commit()
        self._json(200, {"id": uid, "name": name, "email": email, "created_at": created})

    def _get_user(self) -> None:
        body, err = self._payload()
        if err:
            self._json(400, {"error": err})
            return
        try:
            uid = int(body.get("id"))
        except (TypeError, ValueError):
            self._json(400, {"error": "id (integer) is required"})
            return
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, email, created_at FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
        if not row:
            self._json(404, {"error": "user not found"})
            return
        self._json(200, {"id": row[0], "name": row[1], "email": row[2], "created_at": row[3]})

    def _list_users(self) -> None:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, email, created_at FROM users ORDER BY id")
            rows = cur.fetchall()
        self._json(
            200,
            {"users": [{"id": r[0], "name": r[1], "email": r[2], "created_at": r[3]} for r in rows]},
        )

    def log_message(self, *args: object) -> None:  # noqa: A002
        pass


if __name__ == "__main__":
    init_schema()
    print(f"confidential-user-store API listening on :{PORT}")
    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
