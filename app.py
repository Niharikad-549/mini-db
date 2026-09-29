"""Local HTTP server and JSON API for the Mini DB visualizer."""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from benchmark import run_benchmark
from database import Database


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_PATH = ROOT / "mini-db.data"


def make_handler(database: Database, benchmark: dict[str, object]):
    class RequestHandler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: object) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _body(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16_384:
                raise ValueError("Request body is too large")
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Request body must be a JSON object")
            return value

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/state":
                    payload = database.state()
                    payload["benchmark"] = benchmark
                    self._json(200, payload)
                elif parsed.path == "/api/get":
                    key = int(query["key"][0])
                    value, trace = database.get(key)
                    self._json(200, {"key": key, "value": value, "trace": trace})
                elif parsed.path == "/api/range":
                    start, end = int(query["start"][0]), int(query["end"][0])
                    self._json(200, {"items": database.range(start, end)})
                elif parsed.path.startswith("/api/"):
                    self._json(404, {"error": "API route not found"})
                else:
                    self._static(parsed.path)
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
                self._json(400, {"error": str(error) or "Invalid request"})

        def do_POST(self) -> None:
            try:
                body = self._body()
                if self.path == "/api/put":
                    key = body.get("key")
                    value = body.get("value")
                    if isinstance(key, bool) or not isinstance(key, int) or not isinstance(value, str):
                        raise ValueError("Provide an integer key and a text value")
                    page_number = database.put(key, value)
                    self._json(200, {"ok": True, "key": key, "page_number": page_number})
                elif self.path == "/api/delete":
                    key = body.get("key")
                    if isinstance(key, bool) or not isinstance(key, int):
                        raise ValueError("Provide an integer key")
                    deleted = database.delete(key)
                    self._json(200, {"ok": deleted, "key": key})
                elif self.path == "/api/reset":
                    database.reset()
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {"error": "API route not found"})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._json(400, {"error": str(error) or "Invalid request"})

        def _static(self, requested_path: str) -> None:
            relative = "index.html" if requested_path == "/" else requested_path.lstrip("/")
            file_path = (STATIC_DIR / relative).resolve()
            if not file_path.is_relative_to(STATIC_DIR.resolve()) or not file_path.is_file():
                self.send_error(404)
                return
            content = file_path.read_bytes()
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format_string: str, *args: object) -> None:
            print(f"{self.log_date_time_string()} {self.address_string()} {format_string % args}")

    return RequestHandler


def main() -> None:
    database = Database(DATA_PATH)
    print("Running the 10,000-record benchmark for the visualizer...")
    benchmark = run_benchmark()
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(database, benchmark))
    print(f"Mini DB is ready at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mini DB server.")
    finally:
        server.server_close()
        database.close()


if __name__ == "__main__":
    main()