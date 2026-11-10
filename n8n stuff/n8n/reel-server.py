#!/usr/bin/env python3
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

WORKDIR = os.environ.get("WORKDIR", "/work")
YT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _qs(self):
        parsed = urlparse(self.path)
        return parsed.path, parse_qs(parsed.query)

    def do_GET(self):
        path, qs = self._qs()
        if path.startswith("/health"):
            self._send(200, {"status": "ok"})
            return
        if path.startswith("/info"):
            video_id = (qs.get("videoId") or [""])[0]
            if not YT_ID.fullmatch(video_id):
                self._send(400, {"ok": False, "error": "invalid video id"})
                return
            env = os.environ.copy()
            env["HOME"] = WORKDIR
            proc = subprocess.run(
                [
                    "yt-dlp",
                    "--print",
                    "%(duration)s",
                    "--skip-download",
                    "--no-playlist",
                    "--no-warnings",
                    "https://www.youtube.com/watch?v=%s" % video_id,
                ],
                cwd=WORKDIR,
                env=env,
                capture_output=True,
                text=True,
                timeout=45,
            )
            raw = (proc.stdout or "").strip().splitlines()
            duration = None
            if raw:
                try:
                    duration = float(raw[-1])
                except ValueError:
                    duration = None
            ok = proc.returncode == 0 and duration is not None
            self._send(
                200 if ok else 500,
                {
                    "ok": ok,
                    "videoId": video_id,
                    "duration": duration,
                    "durationSeconds": int(duration) if duration is not None else None,
                    "isShort": bool(duration is not None and duration <= 60),
                    "stderr": (proc.stderr or "")[-500:],
                },
            )
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/cleanup"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                body = {}
            video_id = str(body.get("videoId") or "")
            if not YT_ID.fullmatch(video_id):
                self._send(400, {"ok": False, "error": "invalid video id"})
                return
            self._send(200, {"ok": True, "removed": self._cleanup(video_id)})
            return
        if self.path.startswith("/short"):
            self._short()
            return
        if not self.path.startswith("/prep"):
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "invalid json"})
            return
        video_id = str(body.get("videoId") or "")
        is_short = body.get("isShort")
        short = "true" if is_short in (True, "true", "1", 1) else "false"
        if not YT_ID.fullmatch(video_id):
            self._send(400, {"ok": False, "error": "invalid video id"})
            return
        env = os.environ.copy()
        env["HOME"] = WORKDIR
        env["WORKDIR"] = WORKDIR
        proc = subprocess.run(
            ["/usr/local/bin/reel-prep.sh", video_id, short],
            cwd=WORKDIR,
            env=env,
            capture_output=True,
            text=True,
        )
        out_path = f"{WORKDIR}/reels-{video_id}.mp4"
        self._send(
            200 if proc.returncode == 0 and os.path.isfile(out_path) else 500,
            {
                "ok": proc.returncode == 0 and os.path.isfile(out_path),
                "path": out_path if proc.returncode == 0 else "",
                "stdout": (proc.stdout or "")[-500:],
                "stderr": (proc.stderr or "")[-2000:],
            },
        )

    def _short(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "invalid json"})
            return
        video_id = str(body.get("videoId") or "")
        start = str(body.get("start", "auto")).strip().lower() or "auto"
        seconds = str(body.get("seconds", 30)).strip()
        if not YT_ID.fullmatch(video_id):
            self._send(400, {"ok": False, "error": "invalid video id"})
            return
        if not (start == "auto" or start.isdigit()) or not seconds.isdigit() or not 5 <= int(seconds) <= 170:
            self._send(400, {"ok": False, "error": "invalid start/seconds"})
            return
        env = os.environ.copy()
        env["HOME"] = WORKDIR
        env["WORKDIR"] = WORKDIR
        for key, name, biggest, smallest in (("hook", "HOOK", 110, 44), ("cta", "CTA", 66, 36)):
            text = re.sub(r"\s+", " ", str(body.get(key) or "")).strip()[:60]
            env.pop(name, None)
            if text:
                env[name] = text
                env[name + "_FS"] = str(max(smallest, min(biggest, int(960 / (0.68 * len(text))))))
        proc = subprocess.run(
            ["/usr/local/bin/short-prep.sh", video_id, start, seconds],
            cwd=WORKDIR,
            env=env,
            capture_output=True,
            text=True,
        )
        out_path = f"{WORKDIR}/ytshort-{video_id}.mp4"
        ok = proc.returncode == 0 and os.path.isfile(out_path)
        self._send(
            200 if ok else 500,
            {
                "ok": ok,
                "path": out_path if ok else "",
                "stdout": (proc.stdout or "")[-500:],
                "stderr": (proc.stderr or "")[-2000:],
            },
        )

    def _cleanup(self, video_id):
        removed = []
        for name in os.listdir(WORKDIR):
            if name.startswith((f"reel-{video_id}.", f"reels-{video_id}.", f"ytshort-{video_id}.")):
                path = os.path.join(WORKDIR, name)
                try:
                    os.remove(path)
                    removed.append(name)
                except OSError:
                    pass
        return removed

    def do_DELETE(self):
        if not self.path.startswith("/cleanup"):
            self._send(404, {"error": "not found"})
            return
        parsed = self.path.split("?", 1)
        qs = parsed[1] if len(parsed) > 1 else ""
        video_id = ""
        for part in qs.split("&"):
            if part.startswith("videoId="):
                video_id = part.split("=", 1)[1]
        if not YT_ID.fullmatch(video_id):
            self._send(400, {"ok": False, "error": "invalid video id"})
            return
        self._send(200, {"ok": True, "removed": self._cleanup(video_id)})


if __name__ == "__main__":
    os.makedirs(WORKDIR, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
