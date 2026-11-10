# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Local helper for the /convert/ page (prototype).

Browsers cannot download from most data sources because of CORS; Python on the user's own computer can. `owd helper`
starts a minimal HTTP server on 127.0.0.1 only, with a random token for the session. The page finds it through the
link the helper prints (https://openwelldata.org/convert/#helper=PORT.TOKEN; the part after # never leaves the
browser), asks it to download a file from the source, and converts the file in the browser with the same engine as
always. Nothing goes through openwelldata.org.

Security: bound to 127.0.0.1; every request needs the token (Authorization: Bearer); the Host header must be
127.0.0.1 or localhost (DNS rebinding); CORS only for https://openwelldata.org and http://127.0.0.1 / localhost
(tests); one download at a time; public URLs and recipes only, never a login or the acceptance of terms.

Endpoints (JSON unless said otherwise):
  GET  /v1/status                         -> {"owd": version, "datasets": [...ids with an automatic recipe]}
  POST /v1/fetch {"dataset": id}          -> {"files": [members]} for a zip, or the file itself
  POST /v1/fetch {"dataset": id, "member": name}  -> the member's bytes (LAS or CSV)
  POST /v1/fetch {"url": "https://..."}   -> the file's bytes
  POST /v1/fetch {"source": id, "file": name}  -> a catalogue source with a public direct download
                                             (fichas/download_methods.csv), file or zip listing as above
"""
import hmac
import json
import re
import secrets
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import toolkit

PAGE = "https://openwelldata.org/convert/"
ALLOWED_ORIGINS = re.compile(r"^(https://openwelldata\.org|http://(127\.0\.0\.1|localhost)(:\d+)?)$")
MAX_BYTES = 300 * 1024 * 1024
TEXT_MEMBER = re.compile(r"\.(las|csv|txt)$", re.I)


class Helper(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=0, token=None, page=PAGE, opener=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = token or secrets.token_urlsafe(24)
        self.page = page
        self.lock = threading.Lock()
        self.opener = opener

    @property
    def link(self):
        return f"{self.page}#helper={self.server_address[1]}.{self.token}"


class Handler(BaseHTTPRequestHandler):
    server_version = "owd-helper"

    def log_message(self, fmt, *args):      # quiet: the terminal shows only what the user needs
        pass

    def _cors(self):
        o = self.headers.get("Origin")
        if o and ALLOWED_ORIGINS.match(o):
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Expose-Headers", "Content-Disposition, X-OWD-File")

    def _send(self, code, body, ctype="application/json", name=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if name:
            self.send_header("X-OWD-File", name)
        self.end_headers()
        self.wfile.write(data)

    def _guard(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._send(403, {"error": "host not allowed"})
            return False
        o = self.headers.get("Origin")
        if o and not ALLOWED_ORIGINS.match(o):
            self._send(403, {"error": "origin not allowed"})
            return False
        auth = self.headers.get("Authorization") or ""
        if not hmac.compare_digest(auth, "Bearer " + self.server.token):
            self._send(401, {"error": "token missing or wrong; open the link printed by `owd helper`"})
            return False
        return True

    def do_OPTIONS(self):
        o = self.headers.get("Origin")
        if not o or not ALLOWED_ORIGINS.match(o):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        if not self._guard():
            return
        if self.path != "/v1/status":
            return self._send(404, {"error": "not found"})
        from . import __version__, recipes
        auto = [k for k, r in recipes.recipes().items() if r.get("download") == "auto"]
        self._send(200, {"owd": __version__, "datasets": auto})

    def do_POST(self):
        if not self._guard():
            return
        if self.path != "/v1/fetch":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad JSON"})
        if not self.server.lock.acquire(blocking=False):
            return self._send(429, {"error": "one download at a time: wait for the current one"})
        try:
            return self._fetch(req)
        except toolkit.SourceClosed as e:
            return self._send(502, {"error": str(e), "closed": True})
        except Exception as e:                       # reported to the page, never hidden
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        finally:
            self.server.lock.release()

    def _fetch(self, req):
        from . import recipes
        if req.get("url"):
            p = toolkit.fetch_url(req["url"], cache=True, notify=lambda *_: None, opener=self.server.opener)
            return self._file(p.read_bytes() if p.stat().st_size <= MAX_BYTES else None, p.name)
        if req.get("source"):
            rows = toolkit.download_methods().get(req["source"]) or []
            row = next((r for r in rows if r.get("method") in toolkit.OPEN_METHODS and r.get("example_file_url")), None)
            if row is None:
                rec = toolkit.source_record(req["source"]) or {}
                m = rows[0].get("method") if rows else "unknown"
                return self._send(409, {"error": f"{req['source']} {toolkit.CLOSED.get(m, 'has no direct public file')}",
                                        "closed": True, "source": rec.get("url")})
            url, member = toolkit.source_url(row, req.get("file"))
            p = toolkit.fetch_url(url, cache=True, notify=lambda *_: None, opener=self.server.opener)
            return self._zip_or_file(p, req.get("member") or member, url)
        ds = req.get("dataset")
        r = recipes.recipes().get(ds or "")
        if not r:
            return self._send(404, {"error": f"no recipe for {ds!r}"})
        if r.get("download") != "auto":
            return self._send(409, {"error": f"{ds}: the source asks you to download it yourself", "closed": True,
                                    "source": r.get("source"), "terms": r.get("terms")})
        d = recipes.folder(ds) / "original"
        d.mkdir(parents=True, exist_ok=True)
        f = r["files"][0]
        dest = d / f["name"]
        if not dest.exists() or recipes.verify(dest, f):
            recipes.download(f, dest, r["domains"], notify=lambda *_: None)
        return self._zip_or_file(dest, req.get("member"), r.get("source"))

    def _zip_or_file(self, dest, member, source):
        if zipfile.is_zipfile(dest):
            with zipfile.ZipFile(dest) as z:
                names = [m for m in z.namelist() if TEXT_MEMBER.search(m)]
                m = member
                if not m:
                    return self._send(200, {"files": names, "source": source})
                if m not in names:
                    hits = [x for x in names if m in x]
                    if len(hits) != 1:
                        return self._send(200 if hits else 404, {"files": hits, "source": source} if hits else
                                          {"error": f"{m!r} is not in {Path(dest).name}"})
                    m = hits[0]
                info = z.getinfo(m)
                if info.file_size > MAX_BYTES:
                    return self._file(None, m)
                return self._file(z.read(m), Path(m).name)
        return self._file(dest.read_bytes() if dest.stat().st_size <= MAX_BYTES else None, dest.name)

    def _file(self, data, name):
        if data is None:
            return self._send(413, {"error": f"{name} is larger than {MAX_BYTES // 2**20} MB: convert it with "
                                             f"`owd convert` on this computer instead"})
        return self._send(200, data, "application/octet-stream", name=name)


def main(a=None):
    port = getattr(a, "port", 0) or 0
    srv = Helper(port)
    print("Open Well Data helper on 127.0.0.1 (this computer only). Downloads run here, conversions in your browser.")
    print(f"Open this link (the token after # stays in your browser): {srv.link}")
    print("Ctrl+C to stop.")
    if not getattr(a, "no_browser", False):
        try:
            webbrowser.open(srv.link)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
