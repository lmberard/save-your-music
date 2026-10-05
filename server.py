#!/usr/bin/env python3
"""save-your-music: local page that turns YouTube or Spotify links into MP3.

Usage: python3 server.py   (then open http://localhost:8765)
"""
import json
import os
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(ROOT, "scripts", "yt_mp3.sh")
INDEX = os.path.join(ROOT, "static", "index.html")
PORT = int(os.environ.get("PORT", "8765"))
ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be",
    "open.spotify.com", "spotify.link",
}
TIMEOUT = 30 * 60  # long mixes take several minutes to convert

# The server may start without the terminal's PATH; yt-dlp and ffmpeg live in Homebrew.
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))


def valid_link(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in ALLOWED_HOSTS


class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        # Only this machine is served, even if another page tries to call this server.
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("localhost", "127.0.0.1")

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.local_request() or self.path.split("?")[0] != "/":
            self.send_error(404)
            return
        with open(INDEX, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self.local_request() or self.path != "/api/download":
            self.send_error(404)
            return
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            self.send_json(415, {"error": "Expected JSON."})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            url = str(json.loads(self.rfile.read(length)).get("url", "")).strip()
        except (ValueError, AttributeError):
            self.send_json(400, {"error": "Invalid request."})
            return
        if not valid_link(url):
            self.send_json(400, {"error": "Not a YouTube or Spotify link."})
            return

        tmp = tempfile.mkdtemp(prefix="save-your-music-")
        try:
            try:
                result = subprocess.run([SCRIPT, url, tmp], capture_output=True, text=True,
                                        env=ENV, timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                self.send_json(504, {"error": "The download took too long and was cancelled."})
                return
            files = [f for f in os.listdir(tmp) if f.endswith(".mp3")]
            if result.returncode != 0 or not files:
                lines = [l for l in (result.stderr + result.stdout).replace("\r", "\n").splitlines()
                         if l.strip() and not l.startswith("[download]")]
                message = lines[-1] if lines else "Could not download."
                # The script suggests command-line options that don't exist on the page.
                if " Use --list" in message:
                    message = message.split(" Use --list")[0] + " Only single tracks can be downloaded here."
                self.send_json(502, {"error": message})
                return
            path = os.path.join(tmp, files[0])
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % files[0])
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the tab was closed mid-download
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def log_message(self, fmt, *args):
        print("%s  %s" % (self.log_date_time_string(), fmt % args), flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("save-your-music at http://localhost:%d  (Ctrl+C to stop)" % PORT, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
