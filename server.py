#!/usr/bin/env python3
"""save-your-music: página local que convierte links de YouTube o Spotify en MP3.

Uso: python3 server.py   (y abrir http://localhost:8765)
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
TIMEOUT = 30 * 60  # los mixes largos tardan varios minutos en convertirse

# El servidor puede arrancar sin el PATH de la terminal; yt-dlp y ffmpeg viven en Homebrew.
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))


def valid_link(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in ALLOWED_HOSTS


class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        # Solo se atiende a la propia máquina, aunque otra página intente llamar a este servidor.
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
            self.send_json(415, {"error": "Se esperaba JSON."})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            url = str(json.loads(self.rfile.read(length)).get("url", "")).strip()
        except (ValueError, AttributeError):
            self.send_json(400, {"error": "Pedido inválido."})
            return
        if not valid_link(url):
            self.send_json(400, {"error": "No es un link de YouTube ni de Spotify."})
            return

        tmp = tempfile.mkdtemp(prefix="save-your-music-")
        try:
            try:
                result = subprocess.run([SCRIPT, url, tmp], capture_output=True, text=True,
                                        env=ENV, timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                self.send_json(504, {"error": "La descarga tardó demasiado y se canceló."})
                return
            files = [f for f in os.listdir(tmp) if f.endswith(".mp3")]
            if result.returncode != 0 or not files:
                lines = [l for l in (result.stderr + result.stdout).replace("\r", "\n").splitlines()
                         if l.strip() and not l.startswith("[download]")]
                message = lines[-1] if lines else "No se pudo descargar."
                # El script sugiere opciones de consola que en la página no existen.
                if " Usar --list" in message:
                    message = message.split(" Usar --list")[0] + " Desde acá solo se bajan temas sueltos."
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
            pass  # la pestaña se cerró a mitad de la descarga
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def log_message(self, fmt, *args):
        print("%s  %s" % (self.log_date_time_string(), fmt % args), flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("save-your-music en http://localhost:%d  (Ctrl+C para cerrar)" % PORT, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
