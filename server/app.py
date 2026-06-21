from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class LatestImageHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/", "/latest.png"}:
            self.send_error(404)
            return

        image = Path(__file__).resolve().parents[1] / "renderer" / "latest.png"
        if not image.exists():
            self.send_error(404, "latest.png has not been rendered yet")
            return

        data = image.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8080), LatestImageHandler)
    print("Serving latest.png at http://127.0.0.1:8080/latest.png")
    server.serve_forever()


if __name__ == "__main__":
    main()
