import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class LatestImageHandler(BaseHTTPRequestHandler):
    project_root = Path(__file__).resolve().parents[1]
    server_version = "MorningDesk/1.0"

    @property
    def image_path(self):
        return self.project_root / "renderer" / "latest.png"

    @property
    def content_path(self):
        return self.project_root / "content" / "latest.json"

    def do_HEAD(self):
        if self.path in {"/", "/latest.png"}:
            self.serve_image(include_body=False)
            return
        if self.path == "/health.json":
            self.serve_health(include_body=False)
            return
        self.send_error(404)

    def do_GET(self):
        if self.path in {"/", "/latest.png"}:
            self.serve_image(include_body=True)
            return
        if self.path == "/health.json":
            self.serve_health(include_body=True)
            return
        self.send_error(404)

    def serve_image(self, include_body):
        if not self.image_path.exists():
            self.send_error(404, "latest.png has not been rendered yet")
            return

        data = self.image_path.read_bytes()
        etag = f'"{hashlib.sha256(data).hexdigest()}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("ETag", etag)
        self.end_headers()
        if include_body:
            self.wfile.write(data)

    def serve_health(self, include_body):
        generated_at = None
        if self.content_path.exists():
            try:
                generated_at = json.loads(
                    self.content_path.read_text()
                ).get("generated_at")
            except (OSError, json.JSONDecodeError):
                pass

        payload = {
            "status": "ok" if self.image_path.exists() else "degraded",
            "generated_at": generated_at,
            "image_ready": self.image_path.exists(),
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(data)

    def log_message(self, format, *args):
        if os.environ.get("MD_SERVER_QUIET") != "1":
            super().log_message(format, *args)


def create_handler(root):
    return type(
        "ConfiguredLatestImageHandler",
        (LatestImageHandler,),
        {"project_root": Path(root)},
    )


def main():
    host = os.environ.get("MD_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("MD_SERVER_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), LatestImageHandler)
    print(f"Serving latest.png at http://{host}:{port}/latest.png")
    server.serve_forever()


if __name__ == "__main__":
    main()
