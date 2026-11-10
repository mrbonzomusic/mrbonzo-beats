#!/usr/bin/env python3
"""Panel for picking a YouTube video and sending it through the existing n8n post/short workflows."""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import threading
import time
import traceback
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from captions import (
    caption_fb,
    caption_fb_archive,
    caption_social,
    caption_social_archive,
    short_description_seo,
    short_title_seo,
    watch_url,
)
import uploader
import uploader_ui
from campaigns import DAYS as CAMPAIGN_DAYS
from campaigns import DEFAULTS as CAMPAIGN_DEFAULTS
from campaigns import normalize_campaign, patch_weekly_workflow
from workflow_patch import (
    CRED_NAME,
    FILES,
    HEADER,
    SPECS,
    missing_sensitive_credentials,
    patch_workflow,
)

PASSWORD = os.environ.get("PANEL_PASSWORD", "")
API_KEY = os.environ.get("N8N_API_KEY", "").strip()
WEBHOOK_SECRET = os.environ.get("N8N_PANEL_WEBHOOK_SECRET", "").strip()
N8N = os.environ.get("N8N_BASE_URL", "http://n8n:5678").rstrip("/")
YT_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_BACKUP_REPO", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_BACKUP_TOKEN", "").strip()
N8N_IMAGE = os.environ.get("N8N_IMAGE", "docker.n8n.io/n8nio/n8n:latest")
DATA = os.environ.get("DATA_DIR", "/data")
WORKFLOW_DIR = os.environ.get("WORKFLOW_DIR", "/workflows")
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))
DB_PATH = os.path.join(DATA, "panel.sqlite")
REPO_DIR = os.path.join(DATA, "repo")
SECRET_MARK = os.path.join(DATA, "webhook.secret.sha256")
SESS_TTL = 30 * 86400
CATALOG_TTL = 20 * 60
CATALOG_MAX = 500
YT_LINK_RE = re.compile(r"(?:watch\?v=|/shorts/)([A-Za-z0-9_-]{11})")
YT_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DBLOCK = threading.Lock()
BACKUP_LOCK = threading.Lock()
SYNC = {"at": None, "ok": None, "message": "Δεν έχει τρέξει ακόμα.", "workflows": []}
WF_IDS = {}
WF_ALL = []
WF_INDEX_AT = 0.0
WF_INDEX_ERR = ""
WF_TTL = 20
WF_LOCK = threading.Lock()

CHANNELS = {
    "mrbonzomusic": {
        "label": "Mr. Bonzo Music",
        "channel_id": "UCAPju2g7sZ4z0qwMhrkhYng",
        "uploads": "UUAPju2g7sZ4z0qwMhrkhYng",
        "hook": "NEW MUSIC ♪",
        "cta": "Full video on the channel ▶",
    },
    "mrbonzobeats": {
        "label": "Mr. Bonzo Beats",
        "channel_id": "UCLzRHkxvT9HBMjNPI7L31ZQ",
        "uploads": "UULzRHkxvT9HBMjNPI7L31ZQ",
        "hook": "NEW BEAT ♪",
        "cta": "Full beat on the channel ▶",
    },
}
# weekday: Monday 0. Archive shorts stay off the 8-hour gap queue (priority 2).
ARCHIVE = {
    "mrbonzomusic": {"weekdays": (1,), "hour": 18, "hook": "FROM THE ARCHIVE ♪"},
    "mrbonzobeats": {"weekdays": (0, 2), "hour": 18, "hook": "EARLIER BEAT ♪"},
}
STORY_COPY = {
    "mrbonzomusic": {"hook": "MR. BONZO ♪", "cta": "Link in bio ▶"},
    "mrbonzobeats": {"hook": "TYPE BEAT ♪", "cta": "Link in bio ▶"},
}
POST_ARCHIVE = {
    "mrbonzomusic": {"weekdays": (5,), "hour": 18},
    "mrbonzobeats": {"weekdays": (6,), "hour": 18},
}
KIND_FIELDS = {
    "post": ("post_status", "post_error", "post_execution", "posted_at", "posted"),
    "short": ("short_status", "short_error", "short_execution", "shorted_at", "shorted"),
    "story": ("story_status", "story_error", "story_execution", "storied_at", "storied"),
}
ARCHIVE_KEEP = {"Ey5iovKisIs"}


def post_caption(channel, link, title=""):
    return caption_fb(channel, title, link)


def post_caption_social(channel, title):
    return caption_social(channel, title)


def short_title(channel, title):
    return short_title_seo(channel, title)


def short_description(channel, link, title="", video_id=""):
    return short_description_seo(channel, link, title, video_id)


def spec_for(channel, kind):
    for name, spec in SPECS.items():
        if spec["channel"] == channel and spec["kind"] == kind:
            return name, spec
    raise KeyError((channel, kind))


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def local_now():
    return datetime.now(TZ)


def parse_athens_future(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("Διάλεξε ημερομηνία και ώρα.")
    if text.endswith("Z") or re.search(r"[+-]\d\d:?\d\d$", text):
        moment = parse_iso(text)
        if moment is None:
            raise ValueError("Μη έγκυρη ημερομηνία.")
    else:
        try:
            naive = datetime.fromisoformat(text)
        except ValueError:
            raise ValueError("Μη έγκυρη ημερομηνία.")
        moment = naive.replace(tzinfo=TZ) if naive.tzinfo is None else naive
    if moment <= utcnow():
        raise ValueError("Η ώρα είναι στο παρελθόν.")
    return iso(moment)


def _seconds(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def db():
    os.makedirs(DATA, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with DBLOCK:
        con = db()
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                channel TEXT,
                title TEXT,
                post_status TEXT,
                short_status TEXT,
                post_execution TEXT,
                short_execution TEXT,
                post_error TEXT,
                short_error TEXT,
                posted_at TEXT,
                shorted_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                channel TEXT,
                kind TEXT,
                payload TEXT,
                run_at TEXT,
                priority INTEGER,
                status TEXT,
                execution_id TEXT,
                error TEXT,
                request_id TEXT,
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS catalog (
                channel TEXT PRIMARY KEY,
                fetched_at TEXT,
                payload TEXT
            );
            CREATE TABLE IF NOT EXISTS seen_exec (
                execution_id TEXT PRIMARY KEY,
                workflow TEXT,
                kind TEXT,
                video_id TEXT,
                seen_at TEXT
            );
            CREATE TABLE IF NOT EXISTS catalog_hidden (
                channel TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                hidden_at TEXT,
                PRIMARY KEY (channel, video_id)
            );
            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                external_id TEXT NOT NULL,
                url TEXT,
                page TEXT,
                execution_id TEXT,
                status TEXT NOT NULL,
                method TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(platform, external_id)
            );
            CREATE INDEX IF NOT EXISTS publications_video ON publications(video_id);
            CREATE TABLE IF NOT EXISTS pair_rejects (
                short_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                PRIMARY KEY (short_id, source_id)
            );
            """
        )
        for col, typ in (("progress", "REAL"), ("stage", "TEXT"), ("eta_at", "TEXT")):
            try:
                con.execute("ALTER TABLE jobs ADD COLUMN %s %s" % (col, typ))
            except sqlite3.OperationalError:
                pass
        for col in ("story_status", "story_error", "story_execution", "storied_at"):
            try:
                con.execute("ALTER TABLE videos ADD COLUMN %s TEXT" % col)
            except sqlite3.OperationalError:
                pass
        con.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gap_hours', '8')")
        con.commit()
        con.close()


def setting(key, default=None):
    with DBLOCK:
        con = db()
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        con.close()
    return row["value"] if row else default


def set_setting(key, value):
    with DBLOCK:
        con = db()
        con.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        con.commit()
        con.close()


def gap_hours():
    try:
        hours = int(setting("gap_hours", "8"))
    except (TypeError, ValueError):
        hours = 8
    return min(168, max(1, hours))


def campaign_key(cid):
    return "campaign_" + cid


def load_campaign(cid):
    if cid not in CAMPAIGN_DEFAULTS:
        raise ValueError("Άγνωστη καμπάνια.")
    raw = setting(campaign_key(cid), "")
    data = {}
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    return normalize_campaign(cid, data)


def save_campaign(cid, data):
    cfg = normalize_campaign(cid, data)
    set_setting(campaign_key(cid), json.dumps(cfg, ensure_ascii=False))
    return cfg


def find_workflow_by_name(name):
    items = list_paged("/api/v1/workflows?limit=100")
    live = [item for item in items if item.get("name") == name and item.get("active") and not item.get("archived")]
    if live:
        return live[0]
    copies = [item for item in items if item.get("name") == name and not item.get("archived")]
    return copies[0] if copies else None


def last_workflow_run(name):
    meta = find_workflow_by_name(name)
    if not meta:
        return None
    listing = n8n_request(
        "GET",
        "/api/v1/executions?workflowId=%s&limit=1" % urllib.parse.quote(str(meta["id"])),
    )
    rows = listing.get("data") if isinstance(listing, dict) else listing
    if not rows:
        return None
    item = rows[0]
    return {
        "at": item.get("stoppedAt") or item.get("startedAt") or "",
        "status": item.get("status") or "",
        "id": item.get("id") or "",
    }


def apply_campaign_to_n8n(cfg, cred=None):
    meta = find_workflow_by_name(cfg["name"])
    if not meta:
        raise RuntimeError("Δεν βρέθηκε το workflow «%s» στο n8n." % cfg["name"])
    wf = unwrap_workflow(n8n_request("GET", "/api/v1/workflows/%s" % meta["id"]))
    patch_weekly_workflow(wf, cfg, cred)
    save_workflow(wf)
    return meta.get("id")


def campaigns_overview():
    items = []
    for cid in CAMPAIGN_DEFAULTS:
        cfg = load_campaign(cid)
        last = None
        try:
            last = last_workflow_run(cfg["name"])
        except Exception:
            last = None
        items.append({
            "id": cfg["id"],
            "name": cfg["name"],
            "label": cfg["label"],
            "weekday": cfg["weekday"],
            "hour": cfg["hour"],
            "minute": cfg["minute"],
            "link": cfg["link"],
            "image": cfg["image"],
            "texts": cfg.get("texts") or [],
            "pages": cfg["pages"],
            "last": last,
            "present": bool(find_workflow_by_name(cfg["name"])),
        })
    return {"days": CAMPAIGN_DAYS, "items": items}


def fire_campaign(cid, body):
    cfg = load_campaign(cid)
    pages = [str(item) for item in (body.get("pages") or []) if str(item)]
    allowed = {page["id"] for page in cfg["pages"]}
    pages = [item for item in pages if item in allowed]
    payload = {
        "pages": pages,
        "caption": str(body.get("caption") or "").strip(),
        "image": cfg["image"],
        "link": cfg["link"],
    }
    req = urllib.request.Request(
        N8N + "/webhook/" + cfg["path"],
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    if WEBHOOK_SECRET:
        req.add_header(HEADER, WEBHOOK_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400]
        raise RuntimeError("Webhook %s: %s" % (err.code, detail)) from err
    return {"ok": True, "message": "Στάλθηκε στο n8n."}


def sess_sig(exp):
    return hmac.new(PASSWORD.encode(), ("n8n-panel:%d" % exp).encode(), "sha256").hexdigest()


def sess_new():
    exp = int(time.time()) + SESS_TTL
    return "%d.%s" % (exp, sess_sig(exp))


def sess_ok(token):
    if not PASSWORD or not token:
        return False
    try:
        exp, sig = token.split(".", 1)
        exp = int(exp)
    except ValueError:
        return False
    return exp > time.time() and hmac.compare_digest(sig, sess_sig(exp))


def n8n_request(method, path, body=None, timeout=90):
    if not API_KEY:
        raise RuntimeError("Λείπει το N8N_API_KEY.")
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(N8N + path, data=data, method=method)
    req.add_header("X-N8N-API-KEY", API_KEY)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8") or "null"
            return json.loads(raw)
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:800]
        raise RuntimeError("n8n %s %s → %s %s" % (method, path, err.code, detail)) from err


def unwrap_workflow(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and "nodes" in data and "nodes" not in payload:
        return data
    return payload


def unwrap_record(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and "id" in data and "id" not in payload:
        return data
    return payload


def unwrap_execution(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and "status" in data and "status" not in payload:
        return data
    return payload


def list_paged(path):
    out = []
    cursor = None
    while True:
        joiner = "&" if "?" in path else "?"
        url = path
        if cursor:
            url += "%scursor=%s" % (joiner, urllib.parse.quote(cursor))
        payload = n8n_request("GET", url)
        if isinstance(payload, dict):
            out.extend(payload.get("data") or [])
            cursor = payload.get("nextCursor")
        elif isinstance(payload, list):
            out.extend(payload)
            cursor = None
        else:
            break
        if not cursor:
            break
    return out


NODE_KEYS = {
    "id", "name", "webhookId", "disabled", "notesInFlow", "notes", "type", "typeVersion",
    "executeOnce", "alwaysOutputData", "retryOnFail", "maxTries", "waitBetweenTries",
    "continueOnFail", "onError", "position", "parameters", "credentials",
    "customTelemetryTags", "extendsCredential",
}
SETTING_KEYS = {
    "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
    "saveDataSuccessExecution", "executionTimeout", "errorWorkflow", "timezone",
    "executionOrder", "binaryMode", "callerPolicy", "callerIds", "timeSavedMode",
    "timeSavedPerExecution", "redactionPolicy", "availableInMCP", "customTelemetryTags",
    "credentialResolverId",
}


def save_workflow(wf):
    if not wf.get("nodes") and isinstance(wf.get("activeVersion"), dict):
        wf["nodes"] = wf["activeVersion"].get("nodes") or []
        wf["connections"] = wf["activeVersion"].get("connections") or wf.get("connections") or {}
    settings = {key: value for key, value in (wf.get("settings") or {}).items() if key in SETTING_KEYS}
    settings.setdefault("executionOrder", "v1")
    body = {
        "name": wf["name"],
        "nodes": [{key: value for key, value in node.items() if key in NODE_KEYS} for node in wf.get("nodes") or []],
        "connections": wf.get("connections") or {},
        "settings": settings,
    }
    if wf.get("staticData") is not None:
        body["staticData"] = wf["staticData"]
    if "pinData" in wf:
        body["pinData"] = wf.get("pinData")
    return n8n_request("PUT", "/api/v1/workflows/%s?publishIfActive=true" % wf["id"], body)


def ensure_credential():
    digest = hashlib.sha256(WEBHOOK_SECRET.encode()).hexdigest()
    found = None
    for item in list_paged("/api/v1/credentials?limit=100"):
        if item.get("name") == CRED_NAME and item.get("type") == "httpHeaderAuth":
            found = item
            break
    previous = ""
    if os.path.isfile(SECRET_MARK):
        with open(SECRET_MARK, encoding="utf-8") as handle:
            previous = handle.read().strip()
    if found and previous == digest:
        return {"id": found["id"], "name": found["name"]}
    if found:
        n8n_request("DELETE", "/api/v1/credentials/%s" % found["id"])
    created = unwrap_record(n8n_request("POST", "/api/v1/credentials", {
        "name": CRED_NAME,
        "type": "httpHeaderAuth",
        "data": {"name": HEADER, "value": WEBHOOK_SECRET},
    }))
    with open(SECRET_MARK, "w", encoding="utf-8") as handle:
        handle.write(digest)
    return {"id": created["id"], "name": created.get("name") or CRED_NAME}


def patch_files(cred):
    if not os.path.isdir(WORKFLOW_DIR):
        return []
    written = []
    for name, filename in FILES.items():
        path = os.path.join(WORKFLOW_DIR, filename)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            wf = json.load(handle)
        before = json.dumps(wf, sort_keys=True, ensure_ascii=False)
        patch_workflow(wf, cred)
        after = json.dumps(wf, sort_keys=True, ensure_ascii=False)
        if before == after:
            continue
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(wf, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
        written.append(filename)
    for cid, meta in CAMPAIGN_DEFAULTS.items():
        path = os.path.join(WORKFLOW_DIR, meta["file"])
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            wf = json.load(handle)
        cfg = load_campaign(cid)
        before = json.dumps(wf, sort_keys=True, ensure_ascii=False)
        patch_weekly_workflow(wf, cfg, cred)
        after = json.dumps(wf, sort_keys=True, ensure_ascii=False)
        if before == after:
            continue
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(wf, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
        written.append(meta["file"])
    return written


def _workflow_nodes(item):
    nodes = item.get("nodes") or []
    version = item.get("activeVersion")
    if isinstance(version, dict) and version.get("nodes"):
        nodes = version.get("nodes") or nodes
    return nodes or []


def _webhook_paths(item):
    paths = []
    for node in _workflow_nodes(item):
        typ = (node.get("type") or "").lower()
        if "webhook" not in typ:
            continue
        path = (node.get("parameters") or {}).get("path") or ""
        if path:
            paths.append(str(path).strip("/"))
    return paths


def _index_item(item):
    return {
        "id": item.get("id"),
        "active": bool(item.get("active")),
        "archived": bool(item.get("isArchived")),
        "name": item.get("name") or "",
        "paths": _webhook_paths(item),
    }


def spec_matches(item, name, spec):
    if (item.get("name") or "") == name:
        return True
    want = (spec.get("path") or "").strip("/")
    return bool(want) and want in (item.get("paths") or [])


def refresh_workflow_index(force=False):
    global WF_INDEX_AT, WF_INDEX_ERR
    with WF_LOCK:
        if not force and WF_ALL and (time.time() - WF_INDEX_AT) < WF_TTL:
            return
        grouped = {}
        items = []
        for raw in list_paged("/api/v1/workflows?limit=100"):
            item = _index_item(raw)
            items.append(item)
            grouped.setdefault(item["name"], []).append(item)
        WF_ALL[:] = items
        WF_IDS.clear()
        WF_IDS.update(grouped)
        WF_INDEX_AT = time.time()
        WF_INDEX_ERR = ""


def copies_for(name):
    spec = SPECS.get(name)
    if not spec:
        return list(WF_IDS.get(name) or [])
    hits = [item for item in WF_ALL if spec_matches(item, name, spec)]
    live = [item for item in hits if not item.get("archived")]
    return live or hits


def file_for(name):
    filename = FILES.get(name) or ""
    path = os.path.join(WORKFLOW_DIR, filename) if filename else ""
    return path if path and os.path.isfile(path) else ""


def published_copy(name):
    copies = copies_for(name)
    active = [item for item in copies if item.get("active") and not item.get("archived")]
    if len(active) > 1:
        raise RuntimeError("Υπάρχουν %d ενεργά workflows για «%s». Άφησε μόνο ένα." % (len(active), name))
    if active:
        return active[0]
    live = [item for item in copies if not item.get("archived")]
    return live[0] if live else (copies[0] if copies else None)


def sync_live():
    if not API_KEY:
        SYNC.update(at=iso(utcnow()), ok=False, message="Λείπει το N8N_API_KEY. Στο n8n: Settings → n8n API, με δικαιώματα workflows και credentials.", workflows=[])
        return
    if not WEBHOOK_SECRET:
        SYNC.update(at=iso(utcnow()), ok=False, message="Λείπει το N8N_PANEL_WEBHOOK_SECRET.", workflows=[])
        return
    try:
        refresh_workflow_index(force=True)
        cred = ensure_credential()
        changed = []
        refused = []
        imported = []
        for name in SPECS:
            copies = copies_for(name)
            if not copies:
                try:
                    created = import_workflow(name, cred)
                    imported.append("%s [%s]" % (name, created.get("id")))
                    copies = copies_for(name)
                except Exception as err:
                    refused.append(name + " (δεν υπάρχει στο n8n: %s)" % err)
                    continue
            if not copies:
                refused.append(name + " (δεν υπάρχει στο n8n)")
                continue
            live = [meta for meta in copies if meta.get("active") and not meta.get("archived")]
            if not live:
                live = [meta for meta in copies if not meta.get("archived")][:1]
            for meta in live:
                try:
                    wf = unwrap_workflow(n8n_request("GET", "/api/v1/workflows/%s" % meta["id"]))
                    bad = missing_sensitive_credentials(wf)
                    if bad:
                        refused.append("%s [%s] (λείπουν credentials: %s)" % (name, meta["id"], ", ".join(bad)))
                        continue
                    before = json.dumps(wf, sort_keys=True, default=str)
                    patch_workflow(wf, cred)
                    if json.dumps(wf, sort_keys=True, default=str) != before:
                        save_workflow(wf)
                        changed.append("%s [%s]" % (name, meta["id"]))
                    if SPECS[name]["kind"] == "story" and not meta.get("active"):
                        n8n_request("POST", "/api/v1/workflows/%s/publish" % meta["id"], {})
                        meta["active"] = True
                        changed.append("%s [%s] ενεργό" % (name, meta["id"]))
                except Exception as err:
                    refused.append("%s [%s]: %s" % (name, meta["id"], err))
        for cid in CAMPAIGN_DEFAULTS:
            cfg = load_campaign(cid)
            try:
                apply_campaign_to_n8n(cfg, cred)
                changed.append(cfg["name"])
            except Exception as err:
                refused.append("%s: %s" % (cfg["name"], err))
        written = patch_files(cred)
        refresh_workflow_index(force=True)
        bits = []
        if imported:
            bits.append("Εισάχθηκαν: " + ", ".join(imported))
        if changed:
            bits.append("Ενημερώθηκαν: " + ", ".join(changed))
        elif not imported:
            bits.append("Τα live workflows έχουν ήδη τα webhooks.")
        if written:
            bits.append("Αρχεία: " + ", ".join(written))
        if refused:
            bits.append("Δεν πειράχτηκαν: " + "; ".join(refused))
        SYNC.update(at=iso(utcnow()), ok=not refused, message=" ".join(bits), workflows=workflow_status())
    except Exception as err:
        traceback.print_exc()
        SYNC.update(at=iso(utcnow()), ok=False, message=str(err), workflows=workflow_status())


def workflow_status():
    rows = []
    for name, spec in SPECS.items():
        copies = copies_for(name)
        pick = next((meta for meta in copies if meta.get("active") and not meta.get("archived")), None)
        if not pick:
            pick = next((meta for meta in copies if not meta.get("archived")), None)
        if not pick and copies:
            pick = copies[0]
        rows.append({
            "name": name,
            "channel": spec["channel"],
            "kind": spec["kind"],
            "active": bool(pick and pick.get("active") and not pick.get("archived")),
            "present": bool(pick),
            "id": (pick or {}).get("id") or "",
            "canImport": not pick and bool(file_for(name)),
            "copies": len(copies),
        })
    return rows


def import_workflow(name, cred=None):
    if name not in SPECS:
        raise ValueError("Άγνωστο workflow.")
    path = file_for(name)
    if not path:
        raise RuntimeError("Δεν υπάρχει αρχείο για «%s» στο %s." % (name, WORKFLOW_DIR))
    with open(path, encoding="utf-8") as handle:
        wf = json.load(handle)
    wf["name"] = name
    patch_workflow(wf, cred)
    settings = {key: value for key, value in (wf.get("settings") or {}).items() if key in SETTING_KEYS}
    settings.setdefault("executionOrder", "v1")
    body = {
        "name": name,
        "nodes": [{key: value for key, value in node.items() if key in NODE_KEYS} for node in wf.get("nodes") or []],
        "connections": wf.get("connections") or {},
        "settings": settings,
    }
    created = unwrap_record(n8n_request("POST", "/api/v1/workflows", body))
    refresh_workflow_index(force=True)
    return created


def activate_workflow(name, workflow_id=""):
    refresh_workflow_index(force=True)
    copies = copies_for(name)
    live = [item for item in copies if not item.get("archived")]
    if not live:
        cred = ensure_credential() if WEBHOOK_SECRET else None
        created = import_workflow(name, cred)
        workflow_id = workflow_id or created.get("id") or ""
        copies = copies_for(name)
        live = [item for item in copies if not item.get("archived")]
    pool = live or copies
    if workflow_id:
        meta = next((item for item in pool if item.get("id") == workflow_id), None)
    elif len(pool) == 1:
        meta = pool[0]
    else:
        meta = next((item for item in pool if item.get("active")), None) or (pool[0] if pool else None)
    if not meta or not meta.get("id"):
        raise RuntimeError("Το workflow δεν βρέθηκε στο n8n.")
    n8n_request("POST", "/api/v1/workflows/%s/publish" % meta["id"], {})
    meta["active"] = True
    meta["archived"] = False


def _http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; n8n-panel/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def _stamp_from(value):
    if isinstance(value, (int, float)):
        return int(value)
    parsed = parse_iso(value)
    return int(parsed.timestamp()) if parsed else None


def merge_videos(*groups):
    by_id = {}
    for group in groups:
        for item in group or []:
            vid = (item or {}).get("id")
            if not vid:
                continue
            prev = by_id.get(vid) or {}
            merged = dict(prev)
            for key, val in item.items():
                if val is not None and val != "":
                    merged[key] = val
            by_id[vid] = merged
    videos = list(by_id.values())
    videos.sort(key=lambda item: item.get("timestamp") or 0, reverse=True)
    return videos[:CATALOG_MAX]


def save_catalog(channel, videos):
    payload = json.dumps(videos, ensure_ascii=False)
    fetched = iso(utcnow())
    with DBLOCK:
        con = db()
        con.execute(
            "INSERT INTO catalog (channel, fetched_at, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(channel) DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload",
            (channel, fetched, payload),
        )
        con.commit()
        con.close()
    return fetched


def fetch_rss_videos(channel):
    info = CHANNELS[channel]
    raw = _http_get("https://www.youtube.com/feeds/videos.xml?channel_id=" + info["channel_id"])
    root = ET.fromstring(raw)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    videos = []
    for entry in root.findall("atom:entry", ns):
        node = entry.find("yt:videoId", ns)
        vid = (node.text or "").strip() if node is not None else ""
        if not vid:
            ident = entry.find("atom:id", ns)
            text = (ident.text or "") if ident is not None else ""
            if "yt:video:" in text:
                vid = text.rsplit(":", 1)[-1]
        if not vid:
            continue
        title_node = entry.find("atom:title", ns)
        pub_node = entry.find("atom:published", ns)
        videos.append({
            "id": vid,
            "title": ((title_node.text if title_node is not None else "") or vid).strip(),
            "duration": None,
            "timestamp": _stamp_from(pub_node.text if pub_node is not None else None),
        })
    return videos


def fetch_ytdlp_videos(channel):
    info = CHANNELS[channel]
    urls = [
        "https://www.youtube.com/channel/%s/videos" % info["channel_id"],
        "https://www.youtube.com/playlist?list=" + info["uploads"],
    ]
    last_err = ""
    for url in urls:
        proc = subprocess.run(
            [
                "yt-dlp", "--flat-playlist", "-J", "--no-warnings", "--no-progress",
                "--no-cache-dir", "--playlist-end", "500", url,
            ],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            last_err = (proc.stderr or proc.stdout or "yt-dlp failed")[-500:]
            continue
        raw = json.loads(proc.stdout)
        videos = []
        for entry in raw.get("entries") or []:
            if not entry or not entry.get("id"):
                continue
            videos.append({
                "id": entry["id"],
                "title": entry.get("title") or entry["id"],
                "duration": entry.get("duration"),
                "timestamp": entry.get("timestamp") or entry.get("release_timestamp"),
            })
        if videos:
            return videos
    raise RuntimeError(last_err or "yt-dlp failed")


def adopt_catalog(cached, dumped, rss):
    """A full yt-dlp list replaces the cache. Duration and title survive only for ids still present."""
    by_cache = {item["id"]: item for item in cached or [] if item.get("id")}
    by_rss = {item["id"]: item for item in rss or [] if item.get("id")}
    videos = []
    for item in dumped or []:
        vid = item.get("id")
        if not vid:
            continue
        merged = dict(item)
        for src in (by_cache.get(vid) or {}, by_rss.get(vid) or {}):
            for key in ("duration", "title", "timestamp"):
                if not merged.get(key) and src.get(key):
                    merged[key] = src[key]
        videos.append(merged)
    videos.sort(key=lambda item: item.get("timestamp") or 0, reverse=True)
    return videos[:CATALOG_MAX]


def fetch_catalog(channel):
    cached, _fetched, _fresh = _cached_catalog(channel)
    rss = []
    dumped = []
    rss_err = None
    dump_err = None
    try:
        rss = fetch_rss_videos(channel)
    except Exception as err:
        rss_err = err
        traceback.print_exc()
    try:
        dumped = fetch_ytdlp_videos(channel)
    except Exception as err:
        dump_err = err
        traceback.print_exc()
    if dumped:
        if cached and len(dumped) * 2 < len(cached):
            raise RuntimeError(
                "Η νέα λίστα είναι πολύ μικρή (%d έναντι %d). Έμεινε η προηγούμενη."
                % (len(dumped), len(cached))
            )
        videos = adopt_catalog(cached, dumped, rss)
    else:
        videos = merge_videos(cached, rss)
    if not videos:
        raise RuntimeError(str(dump_err or rss_err or "Άδεια λίστα από το YouTube."))
    save_catalog(channel, videos)
    try:
        note_missing_shorts()
        match_catalogs()
    except Exception:
        traceback.print_exc()
    return videos


FETCHING = {}


def _cached_catalog(channel):
    with DBLOCK:
        con = db()
        row = con.execute("SELECT fetched_at, payload FROM catalog WHERE channel=?", (channel,)).fetchone()
        con.close()
    if not row:
        return [], None, False
    fetched = parse_iso(row["fetched_at"])
    fresh = bool(fetched and (utcnow() - fetched).total_seconds() < CATALOG_TTL)
    try:
        videos = json.loads(row["payload"] or "[]")
    except json.JSONDecodeError:
        videos = []
    return videos, row["fetched_at"], fresh


def _fetch_busy(channel):
    started = FETCHING.get(channel)
    return started is not None and (time.monotonic() - started) < 240


def _start_fetch(channel):
    FETCHING[channel] = time.monotonic()
    threading.Thread(target=_fetch_worker, args=(channel,), daemon=True).start()


def _fetch_worker(channel):
    try:
        fetch_catalog(channel)
    except Exception as err:
        traceback.print_exc()
        set_setting("catalog_error_" + channel, str(err)[:500])
        set_setting("catalog_fail_" + channel, iso(utcnow()))
    else:
        set_setting("catalog_error_" + channel, "")
        set_setting("catalog_fail_" + channel, "")
    finally:
        FETCHING.pop(channel, None)


def _catalog_error(channel, fetched):
    stored = (setting("catalog_error_" + channel, "") or "").strip()
    if not stored:
        return None
    failed = parse_iso(setting("catalog_fail_" + channel, "") or "")
    got = parse_iso(fetched) if fetched else None
    if failed and got and failed < got:
        return None
    return stored


def load_catalog(channel, refresh=False):
    videos, fetched, fresh = _cached_catalog(channel)
    err = None
    if refresh:
        try:
            rss = fetch_rss_videos(channel)
            videos = merge_videos(videos, rss)
            fetched = save_catalog(channel, videos)
        except Exception as exc:
            traceback.print_exc()
            err = str(exc)[-500:]
        if not _fetch_busy(channel):
            _start_fetch(channel)
        return videos, fetched, err, True
    problem = _catalog_error(channel, fetched)
    if fresh:
        return videos, fetched, problem, False
    if _fetch_busy(channel):
        return videos, fetched, problem, True
    failed = parse_iso(setting("catalog_fail_" + channel, "") or "")
    if problem and failed and (utcnow() - failed).total_seconds() < 60:
        return videos, fetched, problem, False
    _start_fetch(channel)
    return videos, fetched, problem, True


def video_rows(ids):
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    with DBLOCK:
        con = db()
        rows = con.execute("SELECT * FROM videos WHERE video_id IN (%s)" % marks, tuple(ids)).fetchall()
        jobs = con.execute(
            "SELECT * FROM jobs WHERE video_id IN (%s) AND status IN ('queued', 'running') ORDER BY id" % marks,
            tuple(ids),
        ).fetchall()
        con.close()
    by_id = {row["video_id"]: dict(row) for row in rows}
    for job in jobs:
        item = by_id.setdefault(job["video_id"], {})
        item["job_" + job["kind"]] = job["status"]
        item["job_id_" + job["kind"]] = job["id"]
        item["job_run_" + job["kind"]] = job["run_at"]
        item["job_error_" + job["kind"]] = job["error"]
        item["job_progress_" + job["kind"]] = job_progress_pct(job)
        item["job_stage_" + job["kind"]] = job_stage_label(job)
        item["job_eta_" + job["kind"]] = job_eta_label(job)
        if job["kind"] == "story":
            try:
                story_payload = json.loads(job["payload"] or "{}")
            except json.JSONDecodeError:
                story_payload = {}
            item["job_hook_story"] = story_payload.get("hook") or ""
            item["job_cta_story"] = story_payload.get("cta") or ""
            item["job_start_story"] = story_payload.get("start") or ""
            item["job_seconds_story"] = story_payload.get("seconds") or 0
    return by_id


def public_video(entry, state, pubs=None):
    state = state or {}
    pubs = [dict(item) for item in (pubs or [])]
    youtube = [item for item in pubs if item.get("platform") == "youtube"]
    first = youtube[0] if youtube else {}
    short_id = first.get("external_id") or ""
    return {
        "id": entry["id"],
        "title": entry["title"],
        "duration": entry.get("duration"),
        "timestamp": entry.get("timestamp"),
        "thumb": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % entry["id"],
        "postStatus": state.get("job_post") or state.get("post_status") or "",
        "shortStatus": state.get("job_short") or state.get("short_status") or "",
        "postError": state.get("post_error") or "",
        "shortError": state.get("short_error") or "",
        "postedAt": state.get("posted_at") or "",
        "shortedAt": state.get("shorted_at") or "",
        "nativeShort": is_native_short(entry),
        "postProgress": state.get("job_progress_post") or 0,
        "shortProgress": state.get("job_progress_short") or 0,
        "postStage": state.get("job_stage_post") or "",
        "shortStage": state.get("job_stage_short") or "",
        "postEta": state.get("job_eta_post") or "",
        "shortEta": state.get("job_eta_short") or "",
        "postJobId": state.get("job_id_post") or 0,
        "shortJobId": state.get("job_id_short") or 0,
        "postRunAt": state.get("job_run_post") or "",
        "shortRunAt": state.get("job_run_short") or "",
        "storyStatus": state.get("job_story") or state.get("story_status") or "",
        "storyError": state.get("story_error") or "",
        "storyProgress": state.get("job_progress_story") or 0,
        "storyStage": state.get("job_stage_story") or "",
        "storyEta": state.get("job_eta_story") or "",
        "storyJobId": state.get("job_id_story") or 0,
        "storyRunAt": state.get("job_run_story") or "",
        "storyHook": state.get("job_hook_story") or "",
        "storyCta": state.get("job_cta_story") or "",
        "storyStart": state.get("job_start_story") or "",
        "storySeconds": state.get("job_seconds_story") or 0,
        "shortVideoId": short_id,
        "shortUrl": first.get("url") or ("https://www.youtube.com/shorts/" + short_id if short_id else ""),
        "publications": [public_publication(item) for item in pubs],
    }


def is_native_short(entry):
    duration = entry.get("duration")
    title = (entry.get("title") or "").lower()
    if isinstance(duration, (int, float)) and duration > 0 and duration <= 60:
        return True
    return "#shorts" in title or "/shorts" in title


PAGE_LABELS = {"mrbonzo": "Mr. Bonzo", "studio": "Purple Sound", "basebox": "BaseBox"}
TITLE_STOP = {
    "mr", "bonzo", "type", "beat", "the", "a", "an", "of", "and", "free",
    "official", "audio", "visualizer", "lyrics", "lyric", "shorts", "short",
}
FB_POST_RE = re.compile(r"^\d{6,}_\d{6,}$")
YT_ANY_RE = re.compile(r"(?:shorts/|watch\?v=|youtu\.be/|embed/|v/)([A-Za-z0-9_-]{11})")
DELETE_WORKFLOW = "Panel Facebook delete"
DELETE_FILE = "facebook-delete.json"
IG_DELETE_WORKFLOW = "Panel Instagram delete"
IG_DELETE_FILE = "instagram-delete.json"
IG_MEDIA_RE = re.compile(r"^\d{8,}$")


def youtube_ready():
    return bool(YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN)


def channel_label(channel):
    return (CHANNELS.get(channel) or {}).get("label") or channel


def public_publication(row):
    item = dict(row)
    platform = item.get("platform") or ""
    page = item.get("page") or ""
    external = item.get("external_id") or ""
    url = item.get("url") or ""
    if platform == "youtube" and external and not url:
        url = "https://www.youtube.com/shorts/" + external
    if platform == "facebook" and external and not url:
        url = "https://www.facebook.com/" + external
    return {
        "platform": platform,
        "externalId": external,
        "url": url,
        "page": page,
        "pageLabel": PAGE_LABELS.get(page, page),
        "status": item.get("status") or "",
        "deletable": platform in ("facebook", "fb_story") or (platform in ("instagram", "ig_story") and bool(IG_MEDIA_RE.match(external))) or (platform == "youtube" and youtube_ready()),
    }


def youtube_id_from(text):
    text = (text or "").strip()
    if YT_VIDEO_ID_RE.match(text):
        return text
    found = YT_ANY_RE.findall(text)
    return found[0] if found else ""


def norm_title(title):
    text = (title or "").lower()
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"#\S+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [token for token in text.split() if len(token) > 1 and token not in TITLE_STOP]


def score_tokens(left, right):
    if not left or not right:
        return 0.0
    a, b = set(left), set(right)
    if a == b:
        return 1.0
    inter = a & b
    if not inter:
        return 0.0
    jacc = len(inter) / len(a | b)
    cover = len(inter) / min(len(a), len(b))
    if cover >= 0.8 and min(len(a), len(b)) >= 3:
        return max(jacc, 0.86)
    return jacc


def catalog_sig():
    bits = []
    for channel in CHANNELS:
        _videos, fetched, _fresh = _cached_catalog(channel)
        bits.append(channel + ":" + (fetched or ""))
    return "|".join(bits)


def _catalog_items():
    shorts, longs = [], []
    for channel in CHANNELS:
        for video in _cached_catalog(channel)[0]:
            vid = video.get("id")
            if not vid:
                continue
            item = {
                "id": vid,
                "title": video.get("title") or "",
                "channel": channel,
                "tokens": norm_title(video.get("title")),
            }
            if is_native_short(video):
                shorts.append(item)
            else:
                longs.append(item)
    return shorts, longs


def _pair_index():
    linked = set()
    rejected = {}
    with DBLOCK:
        con = db()
        rows = con.execute(
            "SELECT external_id FROM publications WHERE platform='youtube' AND status IN ('published', 'deleted')"
        ).fetchall()
        rejects = con.execute("SELECT short_id, source_id FROM pair_rejects").fetchall()
        con.close()
    for row in rows:
        linked.add(row["external_id"])
    for row in rejects:
        rejected.setdefault(row["short_id"], set()).add(row["source_id"])
    return linked, rejected


def iter_pair_scores():
    shorts, longs = _catalog_items()
    linked, rejected = _pair_index()
    for short in shorts:
        if short["id"] in linked or len(short["tokens"]) < 2:
            continue
        blocked = rejected.get(short["id"], ())
        scored = []
        for long in longs:
            if long["id"] == short["id"] or long["id"] in blocked:
                continue
            score = score_tokens(short["tokens"], long["tokens"])
            if score >= 0.55:
                scored.append((score, long))
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[0], 0 if item[1]["channel"] == short["channel"] else 1, item[1]["id"]))
        yield short, scored


def _auto_pair(scored):
    best = scored[0][0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    tied = sum(1 for score, _long in scored if abs(score - best) < 0.001)
    return best >= 0.82 and tied == 1 and (best - second) >= 0.12


def upsert_publication(video_id, platform, external_id, url="", page="", execution_id="", status="published", method="match"):
    if not video_id or not platform or not external_id:
        return
    now = iso(utcnow())
    with DBLOCK:
        con = db()
        row = con.execute(
            "SELECT method, status FROM publications WHERE platform=? AND external_id=?",
            (platform, external_id),
        ).fetchone()
        if row:
            if row["status"] == "deleted" and method != "manual":
                con.close()
                return
            if row["method"] == "manual" and method != "manual":
                con.close()
                return
            if method == "match" and row["method"] == "execution":
                con.close()
                return
            con.execute(
                "UPDATE publications SET video_id=?, url=?, page=?, execution_id=COALESCE(NULLIF(?, ''), execution_id), "
                "status=?, method=?, updated_at=? WHERE platform=? AND external_id=?",
                (video_id, url or "", page or "", execution_id or "", status, method, now, platform, external_id),
            )
        else:
            con.execute(
                "INSERT INTO publications (video_id, platform, external_id, url, page, execution_id, status, method, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (video_id, platform, external_id, url or "", page or "", execution_id or "", status, method, now, now),
            )
        con.commit()
        con.close()


def match_catalogs():
    for short, scored in iter_pair_scores():
        if not _auto_pair(scored):
            continue
        src = scored[0][1]
        upsert_publication(
            src["id"],
            "youtube",
            short["id"],
            url="https://www.youtube.com/shorts/" + short["id"],
            method="match",
            status="published",
        )
    set_setting("match_sig", catalog_sig())


def match_if_stale():
    if not any(_cached_catalog(channel)[0] for channel in CHANNELS):
        return
    if setting("match_sig", "") == catalog_sig():
        return
    match_catalogs()


def note_missing_shorts():
    known = []
    for channel in CHANNELS:
        videos = _cached_catalog(channel)[0]
        if not videos:
            return
        known.append({video["id"] for video in videos if video.get("id")})
    present = set().union(*known)
    now = iso(utcnow())
    with DBLOCK:
        con = db()
        rows = con.execute(
            "SELECT external_id FROM publications WHERE platform='youtube' AND status='published'"
        ).fetchall()
        for row in rows:
            if row["external_id"] not in present:
                con.execute(
                    "UPDATE publications SET status='deleted', updated_at=? "
                    "WHERE platform='youtube' AND external_id=? AND status='published'",
                    (now, row["external_id"]),
                )
        con.commit()
        con.close()


def hidden_ids(channel):
    with DBLOCK:
        con = db()
        rows = con.execute("SELECT video_id FROM catalog_hidden WHERE channel=?", (channel,)).fetchall()
        con.close()
    return {row["video_id"] for row in rows}


def hidden_rows():
    with DBLOCK:
        con = db()
        rows = con.execute(
            "SELECT channel, video_id, title FROM catalog_hidden ORDER BY hidden_at DESC"
        ).fetchall()
        con.close()
    return [
        {
            "channel": row["channel"],
            "channelLabel": channel_label(row["channel"]),
            "videoId": row["video_id"],
            "title": row["title"] or row["video_id"],
        }
        for row in rows
    ]


def set_hidden(channel, video_id, title="", hidden=True):
    if channel not in CHANNELS or not YT_VIDEO_ID_RE.match(video_id or ""):
        raise ValueError("Άγνωστο βίντεο.")
    with DBLOCK:
        con = db()
        if hidden:
            con.execute(
                "INSERT INTO catalog_hidden (channel, video_id, title, hidden_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(channel, video_id) DO UPDATE SET title=excluded.title, hidden_at=excluded.hidden_at",
                (channel, video_id, title or video_id, iso(utcnow())),
            )
        else:
            con.execute("DELETE FROM catalog_hidden WHERE channel=? AND video_id=?", (channel, video_id))
        con.commit()
        con.close()


def hide_everywhere(video_id, title=""):
    for channel in CHANNELS:
        videos = _cached_catalog(channel)[0]
        if any(video.get("id") == video_id for video in videos):
            set_hidden(channel, video_id, title or video_id, True)


def catalog_entry(video_id):
    for channel in CHANNELS:
        for video in _cached_catalog(channel)[0]:
            if video.get("id") == video_id:
                return channel, video
    return "", None


def publication_view(source_ids):
    known = set()
    for channel in CHANNELS:
        known.update(video.get("id") for video in _cached_catalog(channel)[0] if video.get("id"))
    want = set(source_ids)
    with DBLOCK:
        con = db()
        rows = con.execute("SELECT * FROM publications").fetchall()
        con.close()
    items = [dict(row) for row in rows]
    published = [item for item in items if item["status"] == "published"]
    linked_away = set()
    by_source = {}
    by_video = {}
    for item in published:
        by_video.setdefault(item["video_id"], []).append(item)
        if item["platform"] == "youtube" and item["video_id"] in known and item["external_id"] != item["video_id"]:
            linked_away.add(item["external_id"])
        if item["video_id"] in want:
            by_source.setdefault(item["video_id"], []).append(item)
    seen = {vid: {(pub["platform"], pub["external_id"]) for pub in pubs} for vid, pubs in by_source.items()}
    for item in items:
        if item["platform"] != "youtube" or item["status"] not in ("published", "deleted") or item["video_id"] not in want:
            continue
        parent = item["video_id"]
        for child in by_video.get(item["external_id"], []):
            if child["platform"] == "youtube":
                continue
            key = (child["platform"], child["external_id"])
            bag = seen.setdefault(parent, set())
            if key in bag:
                continue
            bag.add(key)
            by_source.setdefault(parent, []).append(child)
    return by_source, linked_away


def present_videos(channel, videos):
    hidden = hidden_ids(channel)
    by_source, linked_away = publication_view(item["id"] for item in videos)
    visible = []
    for item in videos:
        if item["id"] in hidden or item["id"] in linked_away:
            continue
        visible.append(item)
    return visible, by_source


def ambiguous_pairs():
    out = []
    for short, scored in iter_pair_scores():
        if _auto_pair(scored):
            continue
        out.append({
            "shortId": short["id"],
            "shortTitle": short["title"],
            "shortChannel": short["channel"],
            "shortChannelLabel": channel_label(short["channel"]),
            "candidates": [
                {
                    "id": long["id"],
                    "title": long["title"],
                    "channel": long["channel"],
                    "channelLabel": channel_label(long["channel"]),
                }
                for _score, long in scored[:3]
            ],
        })
        if len(out) >= 40:
            break
    return out


def pairs_payload():
    match_if_stale()
    return {"ambiguous": ambiguous_pairs(), "hidden": hidden_rows(), "youtube": youtube_ready()}


def link_manual(source_text, short_text):
    source_id = youtube_id_from(source_text)
    short_id = youtube_id_from(short_text)
    if not source_id or not short_id:
        raise ValueError("Χρειάζεται το long βίντεο και το URL του short.")
    if source_id == short_id:
        raise ValueError("Το short και το long είναι το ίδιο βίντεο.")
    _channel, source = catalog_entry(source_id)
    if not source:
        raise ValueError("Το long βίντεο δεν είναι στη λίστα.")
    if is_native_short(source):
        raise ValueError("Αυτό είναι short. Βάλε το id του long βίντεο.")
    upsert_publication(
        source_id,
        "youtube",
        short_id,
        url="https://www.youtube.com/shorts/" + short_id,
        method="manual",
        status="published",
    )
    with DBLOCK:
        con = db()
        con.execute("DELETE FROM pair_rejects WHERE short_id=? AND source_id=?", (short_id, source_id))
        con.commit()
        con.close()
    return {"ok": True, "sourceId": source_id, "shortId": short_id}


def reject_pair(short_text, source_text):
    short_id = youtube_id_from(short_text)
    source_id = youtube_id_from(source_text)
    if not short_id or not source_id:
        raise ValueError("Λείπει το ζεύγος.")
    with DBLOCK:
        con = db()
        con.execute(
            "INSERT OR IGNORE INTO pair_rejects (short_id, source_id) VALUES (?, ?)",
            (short_id, source_id),
        )
        con.commit()
        con.close()
    return {"ok": True}


def unlink_publication(source_text, short_text):
    source_id = youtube_id_from(source_text)
    short_id = youtube_id_from(short_text)
    if not source_id or not short_id:
        raise ValueError("Λείπει το ζεύγος.")
    with DBLOCK:
        con = db()
        cur = con.execute(
            "DELETE FROM publications WHERE platform='youtube' AND video_id=? AND external_id=?",
            (source_id, short_id),
        )
        if not cur.rowcount:
            con.close()
            raise ValueError("Δεν βρέθηκε αυτό το ζεύγος.")
        con.execute(
            "INSERT OR IGNORE INTO pair_rejects (short_id, source_id) VALUES (?, ?)",
            (short_id, source_id),
        )
        con.commit()
        con.close()
    return {"ok": True}


def publication_owned(video_id, platform, external_id):
    with DBLOCK:
        con = db()
        row = con.execute(
            "SELECT * FROM publications WHERE video_id=? AND platform=? AND external_id=? AND status='published'",
            (video_id, platform, external_id),
        ).fetchone()
        if not row and platform != "youtube":
            row = con.execute(
                "SELECT child.* FROM publications child "
                "JOIN publications parent ON parent.platform='youtube' AND parent.status IN ('published', 'deleted') "
                "AND parent.video_id=? AND parent.external_id=child.video_id "
                "WHERE child.platform=? AND child.external_id=? AND child.status='published'",
                (video_id, platform, external_id),
            ).fetchone()
        con.close()
    return dict(row) if row else None


def mark_publication_deleted(platform, external_id):
    with DBLOCK:
        con = db()
        con.execute(
            "UPDATE publications SET status='deleted', updated_at=? WHERE platform=? AND external_id=?",
            (iso(utcnow()), platform, external_id),
        )
        con.commit()
        con.close()


def youtube_delete(video_id):
    if not youtube_ready():
        raise RuntimeError("Λείπει το YouTube token.")
    if not YT_VIDEO_ID_RE.match(video_id or ""):
        raise ValueError("Άκυρο YouTube id.")
    form = urllib.parse.urlencode({
        "client_id": YT_CLIENT_ID,
        "client_secret": YT_CLIENT_SECRET,
        "refresh_token": YT_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            token = json.loads(res.read().decode("utf-8")).get("access_token") or ""
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("YouTube token %s: %s" % (err.code, detail)) from err
    if not token:
        raise RuntimeError("Το YouTube δεν έδωσε access token.")
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/videos?id=" + urllib.parse.quote(video_id),
        method="DELETE",
    )
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res.read()
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return
        detail = err.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("YouTube %s: %s" % (err.code, detail)) from err


def _workflow_body(wf):
    settings = {key: value for key, value in (wf.get("settings") or {}).items() if key in SETTING_KEYS}
    settings.setdefault("executionOrder", "v1")
    return {
        "name": wf.get("name") or DELETE_WORKFLOW,
        "nodes": [{key: value for key, value in node.items() if key in NODE_KEYS} for node in wf.get("nodes") or []],
        "connections": wf.get("connections") or {},
        "settings": settings,
    }


def ensure_named_workflow(name, filename):
    if not API_KEY:
        raise RuntimeError("Λείπει το API key του n8n.")
    path = os.path.join(WORKFLOW_DIR, filename)
    if not os.path.isfile(path):
        raise RuntimeError("Λείπει το αρχείο %s." % filename)
    with open(path, encoding="utf-8") as handle:
        wf = json.load(handle)
    wf["name"] = name
    if WEBHOOK_SECRET:
        cred = ensure_credential()
        for node in wf.get("nodes") or []:
            if "webhook" in (node.get("type") or ""):
                node["parameters"]["authentication"] = "headerAuth"
                node["credentials"] = {"httpHeaderAuth": {"id": cred["id"], "name": cred.get("name") or CRED_NAME}}
    refresh_workflow_index(force=True)
    meta = find_workflow_by_name(name)
    if not meta:
        created = unwrap_record(n8n_request("POST", "/api/v1/workflows", _workflow_body(wf)))
        workflow_id = created.get("id") or ""
    else:
        workflow_id = meta.get("id") or ""
    if not workflow_id:
        raise RuntimeError("Το workflow «%s» δεν δημιουργήθηκε." % name)
    if not meta or not meta.get("active"):
        n8n_request("POST", "/api/v1/workflows/%s/publish" % workflow_id, {})
        refresh_workflow_index(force=True)
    return workflow_id


def ensure_facebook_delete():
    workflow_id = ensure_named_workflow(DELETE_WORKFLOW, DELETE_FILE)
    path = os.path.join(WORKFLOW_DIR, DELETE_FILE)
    with open(path, encoding="utf-8") as handle:
        wanted = json.load(handle)
    wanted_js = ""
    for node in wanted.get("nodes") or []:
        if node.get("name") == "Delete normalize":
            wanted_js = (node.get("parameters") or {}).get("jsCode") or ""
    if not wanted_js:
        return workflow_id
    live = unwrap_workflow(n8n_request("GET", "/api/v1/workflows/%s" % workflow_id))
    live["id"] = live.get("id") or workflow_id
    for node in live.get("nodes") or []:
        if node.get("name") != "Delete normalize":
            continue
        current = (node.get("parameters") or {}).get("jsCode") or ""
        if current != wanted_js:
            node.setdefault("parameters", {})["jsCode"] = wanted_js
            save_workflow(live)
        break
    return workflow_id


def ensure_instagram_delete():
    workflow_id = ensure_named_workflow(IG_DELETE_WORKFLOW, IG_DELETE_FILE)
    path = os.path.join(WORKFLOW_DIR, IG_DELETE_FILE)
    with open(path, encoding="utf-8") as handle:
        wanted = json.load(handle)
    live = unwrap_workflow(n8n_request("GET", "/api/v1/workflows/%s" % workflow_id))
    names = {node.get("name") for node in live.get("nodes") or []}
    if "Delete result" in names:
        return workflow_id
    live["id"] = live.get("id") or workflow_id
    cred = ensure_credential()
    nodes = []
    for node in wanted.get("nodes") or []:
        copy = {key: value for key, value in node.items() if key in NODE_KEYS}
        if "webhook" in (copy.get("type") or "") and cred.get("id"):
            copy.setdefault("parameters", {})["authentication"] = "headerAuth"
            copy["credentials"] = {"httpHeaderAuth": {"id": cred["id"], "name": cred.get("name") or CRED_NAME}}
        nodes.append(copy)
    live["nodes"] = nodes
    live["connections"] = wanted.get("connections") or {}
    save_workflow(live)
    return workflow_id


def facebook_delete(post_id, page):
    if not (FB_POST_RE.match(post_id or "") or re.fullmatch(r"\d{8,}", post_id or "")):
        raise ValueError("Άκυρο Facebook post id.")
    if page not in PAGE_LABELS:
        raise ValueError("Άγνωστη σελίδα Facebook.")
    if not WEBHOOK_SECRET:
        raise RuntimeError("Λείπει το N8N_PANEL_WEBHOOK_SECRET.")
    ensure_facebook_delete()
    req = urllib.request.Request(
        N8N + "/webhook/facebook-delete",
        data=json.dumps({"postId": post_id, "page": page}).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header(HEADER, WEBHOOK_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            res.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400]
        raise RuntimeError("Facebook %s: %s" % (err.code, detail)) from err


def instagram_delete(media_id):
    if not IG_MEDIA_RE.match(media_id or ""):
        raise ValueError("Άκυρο Instagram media id.")
    if not WEBHOOK_SECRET:
        raise RuntimeError("Λείπει το N8N_PANEL_WEBHOOK_SECRET.")
    ensure_instagram_delete()
    req = urllib.request.Request(
        N8N + "/webhook/instagram-delete",
        data=json.dumps({"mediaId": media_id}).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header(HEADER, WEBHOOK_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            res.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400]
        raise RuntimeError("Instagram %s: %s" % (err.code, detail)) from err


def apply_remote_delete(body):
    video_id = youtube_id_from(body.get("videoId") or "")
    channel = (body.get("channel") or "").strip()
    if channel not in CHANNELS or not video_id:
        raise ValueError("Άγνωστο βίντεο.")
    did = False
    if body.get("hide"):
        set_hidden(channel, video_id, (body.get("title") or "").strip(), True)
        did = True
    youtube_ids = body.get("youtube") or []
    if isinstance(youtube_ids, str):
        youtube_ids = [youtube_ids]
    for external_id in youtube_ids:
        external_id = youtube_id_from(str(external_id))
        pub = publication_owned(video_id, "youtube", external_id)
        if not pub:
            raise ValueError("Δεν υπάρχει δεμένο YouTube short.")
        youtube_delete(external_id)
        mark_publication_deleted("youtube", external_id)
        _ch, entry = catalog_entry(external_id)
        hide_everywhere(external_id, (entry or {}).get("title") or external_id)
        did = True
    facebook_ids = body.get("facebook") or []
    if isinstance(facebook_ids, str):
        facebook_ids = [facebook_ids]
    for external_id in facebook_ids:
        external_id = str(external_id or "").strip()
        pub = publication_owned(video_id, "facebook", external_id)
        if not pub:
            raise ValueError("Το Facebook post δεν ανήκει σε αυτό το βίντεο.")
        facebook_delete(external_id, pub.get("page") or "")
        mark_publication_deleted("facebook", external_id)
        did = True
    instagram_ids = body.get("instagram") or []
    if isinstance(instagram_ids, str):
        instagram_ids = [instagram_ids]
    for external_id in instagram_ids:
        external_id = str(external_id or "").strip()
        pub = publication_owned(video_id, "instagram", external_id)
        if not pub:
            raise ValueError("Το Instagram reel δεν ανήκει σε αυτό το βίντεο.")
        instagram_delete(external_id)
        mark_publication_deleted("instagram", external_id)
        did = True
    for external_id in body.get("igStories") or []:
        external_id = str(external_id or "").strip()
        pub = publication_owned(video_id, "ig_story", external_id)
        if not pub:
            raise ValueError("Το Instagram story δεν ανήκει σε αυτό το βίντεο.")
        instagram_delete(external_id)
        mark_publication_deleted("ig_story", external_id)
        did = True
    for external_id in body.get("fbStories") or []:
        external_id = str(external_id or "").strip()
        pub = publication_owned(video_id, "fb_story", external_id)
        if not pub:
            raise ValueError("Το Facebook story δεν ανήκει σε αυτό το βίντεο.")
        facebook_delete(external_id, pub.get("page") or "mrbonzo")
        mark_publication_deleted("fb_story", external_id)
        did = True
    if not did:
        raise ValueError("Δεν επιλέχθηκε ενέργεια.")
    return {"ok": True}


def apply_pairs(body):
    action = (body.get("action") or "").strip()
    if action == "confirm":
        return link_manual(body.get("sourceId") or "", body.get("shortId") or "")
    if action == "manual":
        return link_manual(body.get("sourceId") or "", body.get("url") or body.get("shortId") or "")
    if action == "reject":
        return reject_pair(body.get("shortId") or "", body.get("sourceId") or "")
    if action == "unlink":
        return unlink_publication(body.get("sourceId") or "", body.get("shortId") or "")
    if action == "hide":
        set_hidden(body.get("channel") or "", youtube_id_from(body.get("videoId") or ""), body.get("title") or "", True)
        return {"ok": True}
    if action == "unhide":
        set_hidden(body.get("channel") or "", youtube_id_from(body.get("videoId") or ""), "", False)
        return {"ok": True}
    raise ValueError("Άγνωστη ενέργεια.")


def page_key(name):
    low = (name or "").lower()
    if "basebox" in low:
        return "basebox"
    if "purple" in low or "studio" in low:
        return "studio"
    if "bonzo" in low:
        return "mrbonzo"
    return ""


def facebook_post_id(js):
    if not isinstance(js, dict):
        return ""
    for key in ("post_id", "id"):
        val = str(js.get(key) or "").strip()
        if FB_POST_RE.match(val):
            return val
    return ""


def iter_node_json(detail):
    run = execution_run_data(detail)
    for name, attempts in (run or {}).items():
        if not isinstance(attempts, list):
            continue
        for attempt in attempts:
            data = (attempt or {}).get("data") or {}
            main = data.get("main") or []
            if not isinstance(main, list):
                continue
            for branch in main:
                if not isinstance(branch, list):
                    continue
                for item in branch:
                    js = item.get("json") if isinstance(item, dict) else None
                    if isinstance(js, dict):
                        yield name, js


def harvest_publications(detail, execution_id):
    preferred = set()
    found = set()
    collect_video_ids(detail, found, preferred)
    source = next(iter(sorted(preferred or found)), "")
    if not source:
        return
    for name, js in iter_node_json(detail):
        low = (name or "").lower()
        if "facebook" in low and "check" not in low and "merge" not in low:
            post_id = facebook_post_id(js)
            page = page_key(name)
            if post_id and page:
                upsert_publication(
                    source, "facebook", post_id,
                    url="https://www.facebook.com/" + post_id,
                    page=page, execution_id=execution_id, method="execution",
                )
        elif "instagram" in low and "create" not in low:
            ext = str(js.get("id") or "").strip()
            url = ""
            for key in ("permalink", "url"):
                val = js.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    url = val
                    break
            if ext.isdigit() and len(ext) >= 8:
                upsert_publication(source, "instagram", ext, url=url, execution_id=execution_id, method="execution")
            elif url:
                upsert_publication(source, "instagram", url, url=url, execution_id=execution_id, method="execution")
        elif "tiktok" in low:
            blob = json.dumps(js, ensure_ascii=False)
            for url in re.findall(r"https?://\S*tiktok\.com\S*", blob):
                url = url.rstrip(".,)")
                upsert_publication(source, "tiktok", url, url=url, execution_id=execution_id, method="execution")
        elif name == "IG story publish":
            ext = str(js.get("id") or "").strip()
            if IG_MEDIA_RE.match(ext):
                upsert_publication(
                    source, "ig_story", ext, page="mrbonzo",
                    execution_id=execution_id, method="story",
                )
        elif name == "FB story start":
            story_video = str(js.get("video_id") or "").strip()
            if re.fullmatch(r"\d{8,}", story_video):
                upsert_publication(
                    source, "fb_story", story_video,
                    page="mrbonzo", execution_id=execution_id, method="story",
                )
        elif "youtube" in low and "short" in low:
            blob = json.dumps(js, ensure_ascii=False)
            for sid in re.findall(r"/shorts/([A-Za-z0-9_-]{11})", blob):
                if sid != source and YT_VIDEO_ID_RE.match(sid):
                    upsert_publication(
                        source, "youtube", sid,
                        url="https://www.youtube.com/shorts/" + sid,
                        execution_id=execution_id, method="execution",
                    )


def publication_workflows():
    names = list(SPECS.keys())
    for cfg in CAMPAIGN_DEFAULTS.values():
        name = cfg.get("name")
        if name and name not in names:
            names.append(name)
    return names


def publication_tick():
    if not API_KEY:
        return False
    refresh_workflow_index()
    for name in publication_workflows():
        meta = find_workflow_by_name(name) or {}
        workflow_id = str(meta.get("id") or "")
        if not workflow_id:
            continue
        done_key = "pub_done_" + workflow_id
        cursor_key = "pub_cursor_" + workflow_id
        if setting(done_key, "") == "1":
            continue
        cursor = setting(cursor_key, "") or ""
        path = "/api/v1/executions?workflowId=%s&limit=8" % urllib.parse.quote(workflow_id)
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        payload = n8n_request("GET", path, timeout=60)
        items = payload.get("data") if isinstance(payload, dict) else payload
        next_cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
        for item in items or []:
            if str(item.get("status") or "").lower() != "success":
                continue
            exec_id = str(item.get("id") or "")
            if not exec_id:
                continue
            try:
                detail = unwrap_execution(n8n_request("GET", "/api/v1/executions/%s?includeData=true" % exec_id, timeout=60))
                harvest_publications(detail, exec_id)
            except Exception:
                traceback.print_exc()
        if next_cursor:
            set_setting(cursor_key, next_cursor)
            return True
        set_setting(cursor_key, "")
        set_setting(done_key, "1")
        return True
    return False


def mark_video_done(video_id, channel, title, kind, execution_id="", when=""):
    if not video_id or kind not in KIND_FIELDS:
        return
    remember_video(channel, video_id, title or video_id)
    column, _err, exec_col, at_col, status = KIND_FIELDS[kind]
    stamp = when or iso(utcnow())
    with DBLOCK:
        con = db()
        row = con.execute("SELECT * FROM videos WHERE video_id=?", (video_id,)).fetchone()
        if row and row[column] in (status, "reset"):
            con.close()
            return
        active = con.execute(
            "SELECT id FROM jobs WHERE video_id=? AND kind=? AND status IN ('queued','running')",
            (video_id, kind),
        ).fetchone()
        if active:
            con.close()
            return
        sets = ["%s=?" % column, "%s=?" % at_col, "updated_at=?", "channel=?", "title=?"]
        args = [status, stamp, iso(utcnow()), channel, title or video_id]
        if execution_id:
            sets.append("%s=?" % exec_col)
            args.append(str(execution_id))
        args.append(video_id)
        con.execute("UPDATE videos SET %s WHERE video_id=?" % ", ".join(sets), args)
        con.commit()
        con.close()


def sync_jobs_to_videos():
    with DBLOCK:
        con = db()
        rows = con.execute("SELECT * FROM jobs WHERE status='done'").fetchall()
        con.close()
    for row in rows:
        payload = {}
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        mark_video_done(
            row["video_id"],
            row["channel"],
            payload.get("title") or row["video_id"],
            row["kind"],
            row["execution_id"] or "",
            row["finished_at"] or "",
        )


def collect_video_ids(obj, found=None, preferred=None):
    found = set() if found is None else found
    preferred = set() if preferred is None else preferred
    if isinstance(obj, dict):
        for key, val in obj.items():
            low = str(key).lower()
            if low == "videoid" and isinstance(val, str) and YT_VIDEO_ID_RE.match(val):
                preferred.add(val)
                found.add(val)
            elif low in ("link", "url", "webpage_url") and isinstance(val, str):
                found.update(YT_LINK_RE.findall(val))
            else:
                collect_video_ids(val, found, preferred)
    elif isinstance(obj, list):
        for item in obj:
            collect_video_ids(item, found, preferred)
    elif isinstance(obj, str):
        found.update(YT_LINK_RE.findall(obj))
    return preferred or found


def backfill_tick():
    if not API_KEY:
        return False
    try:
        refresh_workflow_index()
    except Exception:
        traceback.print_exc()
        return False
    more = False
    for name, spec in SPECS.items():
        meta = {}
        try:
            meta = published_copy(name) or {}
        except Exception:
            continue
        workflow_id = meta.get("id")
        if not workflow_id:
            continue
        cursor_key = "backfill_cursor_" + workflow_id
        done_key = "backfill_done_" + workflow_id
        done = setting(done_key, "") == "1"
        cursor = "" if done else (setting(cursor_key, "") or "")
        path = "/api/v1/executions?workflowId=%s&limit=25" % urllib.parse.quote(str(workflow_id))
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        try:
            payload = n8n_request("GET", path, timeout=60)
        except Exception:
            traceback.print_exc()
            continue
        items = payload.get("data") if isinstance(payload, dict) else payload
        next_cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
        for item in items or []:
            exec_id = str(item.get("id") or "")
            if not exec_id:
                continue
            with DBLOCK:
                con = db()
                seen = con.execute("SELECT execution_id FROM seen_exec WHERE execution_id=?", (exec_id,)).fetchone()
                con.close()
            if seen:
                continue
            state = str(item.get("status") or "").lower()
            if state in ("error", "crashed", "canceled", "cancelled", "waiting", "running", "new"):
                with DBLOCK:
                    con = db()
                    con.execute(
                        "INSERT OR IGNORE INTO seen_exec (execution_id, workflow, kind, video_id, seen_at) VALUES (?, ?, ?, '', ?)",
                        (exec_id, name, spec["kind"], iso(utcnow())),
                    )
                    con.commit()
                    con.close()
                continue
            try:
                detail = unwrap_execution(n8n_request("GET", "/api/v1/executions/%s?includeData=true" % exec_id, timeout=60))
            except Exception:
                more = True
                continue
            ids = collect_video_ids(detail)
            video_id = next(iter(sorted(ids)), "")
            title = ""
            if video_id:
                blob = json.dumps(detail, default=str)
                match = re.search(r'"title"\s*:\s*"([^"]{3,180})"', blob)
                if match:
                    title = match.group(1)
                mark_video_done(video_id, spec["channel"], title, spec["kind"], exec_id, item.get("stoppedAt") or item.get("startedAt") or "")
            with DBLOCK:
                con = db()
                con.execute(
                    "INSERT OR IGNORE INTO seen_exec (execution_id, workflow, kind, video_id, seen_at) VALUES (?, ?, ?, ?, ?)",
                    (exec_id, name, spec["kind"], video_id, iso(utcnow())),
                )
                con.commit()
                con.close()
        if done:
            pass
        elif next_cursor:
            set_setting(cursor_key, next_cursor)
            more = True
        else:
            set_setting(cursor_key, "")
            set_setting(done_key, "1")
    if not more:
        try:
            more = publication_tick()
        except Exception:
            traceback.print_exc()
    return more


def backfill_story_publications():
    if not API_KEY:
        return
    with DBLOCK:
        con = db()
        rows = con.execute(
            "SELECT video_id, execution_id FROM jobs WHERE kind='story' AND status='done' AND COALESCE(execution_id, '') != ''"
        ).fetchall()
        have = {
            row["video_id"]
            for row in con.execute("SELECT video_id FROM publications WHERE platform='ig_story'")
        }
        have.update(
            row["video_id"]
            for row in con.execute("SELECT video_id FROM videos WHERE story_status='reset'")
        )
        con.close()
    for row in rows:
        if row["video_id"] in have:
            continue
        try:
            detail = unwrap_execution(
                n8n_request("GET", "/api/v1/executions/%s?includeData=true" % row["execution_id"], timeout=60)
            )
            harvest_publications(detail, row["execution_id"])
        except Exception:
            traceback.print_exc()


def backfill_loop():
    time.sleep(4)
    try:
        sync_jobs_to_videos()
    except Exception:
        traceback.print_exc()
    try:
        if API_KEY and WEBHOOK_SECRET:
            ensure_facebook_delete()
            ensure_instagram_delete()
            backfill_story_publications()
    except Exception:
        traceback.print_exc()
    idle = 0
    while True:
        try:
            more = backfill_tick()
        except Exception:
            traceback.print_exc()
            more = False
        if more:
            idle = 0
            time.sleep(2)
            continue
        idle += 1
        time.sleep(60 if idle < 3 else 600)


def remember_video(channel, video_id, title):
    with DBLOCK:
        con = db()
        con.execute(
            "INSERT INTO videos (video_id, channel, title, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(video_id) DO UPDATE SET channel=excluded.channel, title=excluded.title, updated_at=excluded.updated_at",
            (video_id, channel, title, iso(utcnow())),
        )
        con.commit()
        con.close()


def enqueue(body):
    channel = body.get("channel")
    kind = body.get("kind")
    video_id = str(body.get("videoId") or "")
    if channel not in CHANNELS or kind not in KIND_FIELDS:
        raise ValueError("Άγνωστο κανάλι ή ενέργεια.")
    if not video_id or not all(ch.isalnum() or ch in "-_" for ch in video_id):
        raise ValueError("Μη έγκυρο video id.")
    title = str(body.get("title") or video_id)[:180]
    link = "https://www.youtube.com/watch?v=" + video_id
    when = body.get("when") or "now"
    confirm = bool(body.get("confirm"))
    duration = body.get("duration")
    if kind == "short" and isinstance(duration, (int, float)) and duration <= 60 and not confirm:
        raise Confirm("Αυτό μοιάζει ήδη με Short (έως 60s). Το workflow δεν θα κόψει νέο κλιπ.")
    with DBLOCK:
        con = db()
        row = con.execute("SELECT * FROM videos WHERE video_id=?", (video_id,)).fetchone()
        active = con.execute(
            "SELECT id, status FROM jobs WHERE video_id=? AND kind=? AND status IN ('queued','running')",
            (video_id, kind),
        ).fetchone()
        con.close()
    story_update_id = None
    if active:
        if kind == "story" and active["status"] == "queued":
            story_update_id = active["id"]
        elif kind == "story" and active["status"] == "running":
            raise ValueError("Το story τρέχει ήδη.")
        else:
            raise ValueError("Υπάρχει ήδη δουλειά στην ουρά για αυτό το βίντεο.")
    status_key, _err, _exec, _at, done_word = KIND_FIELDS[kind]
    if not story_update_id and row and row[status_key] == done_word and not confirm:
        raise Confirm("Έχει ήδη σταλεί. Να ξανασταλεί;")
    if kind == "post":
        platforms = [item for item in (body.get("platforms") or []) if item in ("facebook", "instagram", "tiktok")]
        if not platforms:
            raise ValueError("Διάλεξε τουλάχιστον μία πλατφόρμα.")
        message = str(body.get("message") or post_caption(channel, link, title))[:4000]
        payload = {
            "videoId": video_id,
            "title": title,
            "link": link,
            "message": message,
            "messageFb": str(body.get("messageFb") or message)[:4000],
            "messageSocial": str(body.get("messageSocial") or post_caption_social(channel, title))[:4000],
            "platforms": platforms,
        }
    elif kind == "story":
        try:
            seconds = int(body.get("seconds") or 30)
        except (TypeError, ValueError):
            raise ValueError("Μη έγκυρη διάρκεια.")
        if not 5 <= seconds <= 60:
            raise ValueError("Το story είναι απόσπασμα 5 έως 60 δευτερολέπτων.")
        if isinstance(duration, (int, float)) and duration > 0 and seconds >= duration:
            raise ValueError("Το story είναι απόσπασμα. Η διάρκεια πρέπει να είναι μικρότερη από το τραγούδι.")
        if isinstance(duration, (int, float)) and duration <= 60 and not confirm:
            raise Confirm("Αυτό μοιάζει ήδη με Short (έως 60s). Το story κόβει απόσπασμα μόνο από μεγαλύτερο τραγούδι.")
        start = str(body.get("start") or "auto").strip().lower() or "auto"
        if start != "auto" and not start.isdigit():
            raise ValueError("Η αρχή είναι auto ή δευτερόλεπτα.")
        hook = body.get("hook")
        if hook is None or not str(hook).strip():
            hook = STORY_COPY[channel]["hook"]
        cta = body.get("cta")
        if cta is None or not str(cta).strip():
            cta = STORY_COPY[channel]["cta"]
        payload = {
            "videoId": video_id,
            "title": title,
            "link": link,
            "start": start,
            "seconds": seconds,
            "hook": str(hook)[:60],
            "cta": str(cta)[:60],
        }
    else:
        try:
            seconds = int(body.get("seconds") or 30)
        except (TypeError, ValueError):
            raise ValueError("Μη έγκυρη διάρκεια.")
        if not 5 <= seconds <= 170:
            raise ValueError("Η διάρκεια του Short πρέπει να είναι 5 έως 170 δευτερόλεπτα.")
        start = str(body.get("start") or "auto").strip().lower() or "auto"
        if start != "auto" and not start.isdigit():
            raise ValueError("Η αρχή είναι auto ή δευτερόλεπτα.")
        payload = {
            "videoId": video_id,
            "title": title,
            "link": link,
            "start": start,
            "seconds": seconds,
            "hook": str(body.get("hook") if body.get("hook") is not None else CHANNELS[channel]["hook"])[:60],
            "cta": str(body.get("cta") if body.get("cta") is not None else CHANNELS[channel]["cta"])[:60],
            "shortTitle": str(body.get("shortTitle") or short_title(channel, title))[:70],
            "shortDescription": str(body.get("shortDescription") or short_description(channel, link, title, video_id))[:2000],
            "skipWait": True,
        }
    if story_update_id and when in ("queue", "later"):
        priority = 2
        run_at = None
    elif when == "now":
        priority = 0
        run_at = iso(utcnow())
    elif when == "at":
        priority = 2 if story_update_id else 1
        run_at = parse_athens_future(body.get("runAt"))
    elif when in ("queue", "later"):
        priority = 1
        run_at = next_slot()
    else:
        raise ValueError("Άγνωστος προγραμματισμός.")
    request_id = "panel-%d-%s" % (int(time.time() * 1000), video_id[:8])
    remember_video(channel, video_id, title)
    encoded = json.dumps(payload, ensure_ascii=False)
    with DBLOCK:
        con = db()
        if story_update_id:
            if run_at is None:
                con.execute(
                    "UPDATE jobs SET payload=? WHERE id=? AND status='queued'",
                    (encoded, story_update_id),
                )
            else:
                con.execute(
                    "UPDATE jobs SET payload=?, run_at=?, priority=? WHERE id=? AND status='queued'",
                    (encoded, run_at, priority, story_update_id),
                )
            job_id = story_update_id
            if run_at is None:
                kept = con.execute("SELECT run_at FROM jobs WHERE id=?", (story_update_id,)).fetchone()
                run_at = kept["run_at"] if kept else ""
        else:
            con.execute(
                "INSERT INTO jobs (video_id, channel, kind, payload, run_at, priority, status, request_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)",
                (video_id, channel, kind, encoded, run_at, priority, request_id, iso(utcnow())),
            )
            job_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit()
        con.close()
    return {"id": job_id, "runAt": run_at, "status": "queued"}


class Confirm(Exception):
    pass


def next_slot():
    with DBLOCK:
        con = db()
        row = con.execute("SELECT MAX(run_at) AS m FROM jobs WHERE status='queued' AND priority=1").fetchone()
        con.close()
    last = parse_iso(row["m"]) if row and row["m"] else None
    moment = utcnow()
    if last is None:
        return iso(moment)
    candidate = last + timedelta(hours=gap_hours())
    if candidate < moment:
        candidate = moment
    return iso(candidate)


def _archive_weekdays(spec):
    days = spec.get("weekdays")
    if days:
        return list(days)
    if "weekday" in spec:
        return [spec["weekday"]]
    return []


def _archive_slots(weekdays, count, taken, hour=18):
    wanted = set(weekdays)
    now = local_now()
    cursor = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if cursor <= now:
        cursor += timedelta(days=1)
    slots = []
    guard = 0
    limit = max(count * 7 + 21, 21)
    while len(slots) < count and guard < limit:
        if cursor.weekday() in wanted:
            stamp = iso(cursor)
            if stamp not in taken:
                slots.append(stamp)
        cursor += timedelta(days=1)
        guard += 1
    if len(slots) < count:
        raise RuntimeError("Δεν βγήκαν αρκετές ημερομηνίες.")
    return slots


def reschedule_archive(channel):
    """Move queued archive shorts of one channel onto its current weekdays, oldest first."""
    spec = ARCHIVE[channel]
    with DBLOCK:
        con = db()
        try:
            rows = con.execute(
                "SELECT id, run_at FROM jobs WHERE channel=? AND kind='short' AND status='queued' AND priority=2 "
                "ORDER BY run_at, id",
                (channel,),
            ).fetchall()
            slots = _archive_slots(_archive_weekdays(spec), len(rows), set(), spec["hour"])
            for row, run_at in zip(rows, slots):
                con.execute("UPDATE jobs SET run_at=? WHERE id=? AND status='queued'", (run_at, row["id"]))
            con.commit()
        finally:
            con.close()
    return {"channel": channel, "moved": len(rows), "first": slots[0] if slots else "", "last": slots[-1] if slots else ""}


def _archive_candidates(channel, skip_ids=None):
    videos, _fetched, _fresh = _cached_catalog(channel)
    if not videos:
        raise ValueError("Η λίστα του %s είναι άδεια. Πάτα Ανανέωση λίστας." % channel_label(channel))
    hidden = hidden_ids(channel)
    skipped = ARCHIVE_KEEP if skip_ids is None else skip_ids
    chosen = []
    for item in videos:
        video_id = item.get("id") or ""
        if not video_id or video_id in hidden or video_id in skipped:
            continue
        seconds = _seconds(item.get("duration"))
        if seconds is None or seconds <= 60:
            continue
        chosen.append(item)
    chosen.sort(key=lambda item: (item.get("timestamp") or 10**18, item["id"]))
    return chosen


def schedule_archive():
    plans = [(channel, ARCHIVE[channel], _archive_candidates(channel)) for channel in ARCHIVE]
    now = iso(utcnow())
    created = []
    with DBLOCK:
        con = db()
        try:
            active = {
                row["video_id"]
                for row in con.execute(
                    "SELECT video_id FROM jobs WHERE kind='short' AND status IN ('queued','running')"
                )
            }
            taken = {channel: set() for channel in ARCHIVE}
            for row in con.execute(
                "SELECT channel, run_at FROM jobs WHERE kind='short' AND status='queued' AND priority=2"
            ):
                if row["channel"] in taken and row["run_at"]:
                    taken[row["channel"]].add(row["run_at"])
            for channel, spec, chosen in plans:
                pending = [item for item in chosen if item["id"] not in active]
                slots = _archive_slots(_archive_weekdays(spec), len(pending), taken[channel], spec["hour"])
                for index, (item, run_at) in enumerate(zip(pending, slots)):
                    video_id = item["id"]
                    title = str(item.get("title") or video_id)[:180]
                    link = "https://www.youtube.com/watch?v=" + video_id
                    payload = {
                        "videoId": video_id,
                        "title": title,
                        "link": link,
                        "start": "auto",
                        "seconds": 30,
                        "hook": spec["hook"],
                        "cta": CHANNELS[channel]["cta"],
                        "shortTitle": short_title(channel, title)[:70],
                        "shortDescription": short_description_seo(channel, link, title, video_id, archive=True)[:2000],
                        "skipWait": True,
                        "archive": True,
                    }
                    request_id = "archive-%s-%d" % (video_id, index)
                    con.execute(
                        "INSERT INTO videos (video_id, channel, title, updated_at) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(video_id) DO UPDATE SET channel=excluded.channel, title=excluded.title, updated_at=excluded.updated_at",
                        (video_id, channel, title, now),
                    )
                    con.execute(
                        "UPDATE videos SET short_status='', short_error='', short_execution='', shorted_at=NULL, updated_at=? "
                        "WHERE video_id=?",
                        (now, video_id),
                    )
                    con.execute(
                        "UPDATE publications SET status='deleted', updated_at=? "
                        "WHERE platform='youtube' AND video_id=? AND status='published'",
                        (now, video_id),
                    )
                    con.execute(
                        "INSERT INTO jobs (video_id, channel, kind, payload, run_at, priority, status, request_id, created_at) "
                        "VALUES (?, ?, 'short', ?, ?, 2, 'queued', ?, ?)",
                        (video_id, channel, json.dumps(payload, ensure_ascii=False), run_at, request_id, now),
                    )
                    active.add(video_id)
                    taken[channel].add(run_at)
                    created.append({"channel": channel, "videoId": video_id, "runAt": run_at, "title": title})
            con.commit()
        finally:
            con.close()
    created.sort(key=lambda item: item["runAt"])
    counts = {channel: sum(1 for item in created if item["channel"] == channel) for channel in ARCHIVE}
    if not created:
        message = "Δεν προστέθηκε τίποτα. Όσα έπρεπε είναι ήδη στην ουρά."
    else:
        message = "Μπήκαν %d shorts. Music %d, Beats %d." % (
            len(created), counts["mrbonzomusic"], counts["mrbonzobeats"],
        )
    return {
        "queued": len(created),
        "music": counts["mrbonzomusic"],
        "beats": counts["mrbonzobeats"],
        "first": created[0]["runAt"] if created else "",
        "last": created[-1]["runAt"] if created else "",
        "message": message,
    }


def schedule_archive_posts():
    plans = [(channel, POST_ARCHIVE[channel], _archive_candidates(channel, skip_ids=set())) for channel in POST_ARCHIVE]
    now = iso(utcnow())
    created = []
    with DBLOCK:
        con = db()
        try:
            active = {
                row["video_id"]
                for row in con.execute(
                    "SELECT video_id FROM jobs WHERE kind='post' AND status IN ('queued','running')"
                )
            }
            taken = {channel: set() for channel in POST_ARCHIVE}
            for row in con.execute(
                "SELECT channel, run_at FROM jobs WHERE kind='post' AND status='queued' AND priority=2"
            ):
                if row["channel"] in taken and row["run_at"]:
                    taken[row["channel"]].add(row["run_at"])
            for channel, spec, chosen in plans:
                pending = [item for item in chosen if item["id"] not in active]
                slots = _archive_slots(_archive_weekdays(spec), len(pending), taken[channel], spec["hour"])
                for index, (item, run_at) in enumerate(zip(pending, slots)):
                    video_id = item["id"]
                    title = str(item.get("title") or video_id)[:180]
                    link = "https://www.youtube.com/watch?v=" + video_id
                    message = caption_fb_archive(channel, title, link)
                    social = caption_social_archive(channel, title)
                    payload = {
                        "videoId": video_id,
                        "title": title,
                        "link": link,
                        "message": message,
                        "messageFb": message,
                        "messageSocial": social,
                        "platforms": ["facebook", "instagram", "tiktok"],
                        "archive": True,
                    }
                    request_id = "archive-post-%s-%d" % (video_id, index)
                    con.execute(
                        "INSERT INTO videos (video_id, channel, title, updated_at) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(video_id) DO UPDATE SET channel=excluded.channel, title=excluded.title, updated_at=excluded.updated_at",
                        (video_id, channel, title, now),
                    )
                    con.execute(
                        "UPDATE videos SET post_status='', post_error='', post_execution='', posted_at=NULL, updated_at=? "
                        "WHERE video_id=?",
                        (now, video_id),
                    )
                    con.execute(
                        "INSERT INTO jobs (video_id, channel, kind, payload, run_at, priority, status, request_id, created_at) "
                        "VALUES (?, ?, 'post', ?, ?, 2, 'queued', ?, ?)",
                        (video_id, channel, json.dumps(payload, ensure_ascii=False), run_at, request_id, now),
                    )
                    active.add(video_id)
                    taken[channel].add(run_at)
                    created.append({"channel": channel, "videoId": video_id, "runAt": run_at, "title": title})
            con.commit()
        finally:
            con.close()
    created.sort(key=lambda item: item["runAt"])
    counts = {channel: sum(1 for item in created if item["channel"] == channel) for channel in POST_ARCHIVE}
    if not created:
        message = "Δεν προστέθηκε τίποτα. Όσα posts έπρεπε είναι ήδη στην ουρά."
    else:
        message = "Μπήκαν %d posts. Music %d, Beats %d." % (
            len(created), counts["mrbonzomusic"], counts["mrbonzobeats"],
        )
    return {
        "queued": len(created),
        "music": counts["mrbonzomusic"],
        "beats": counts["mrbonzobeats"],
        "first": created[0]["runAt"] if created else "",
        "last": created[-1]["runAt"] if created else "",
        "message": message,
    }


def schedule_archive_stories():
    """One story job beside each queued post, at the same time. Safe to call again."""
    if setting("story_archive_filled", "") == "1":
        return {"skipped": True, "queued": 0}
    now = iso(utcnow())
    created = []
    with DBLOCK:
        con = db()
        try:
            active = {
                row["video_id"]
                for row in con.execute(
                    "SELECT video_id FROM jobs WHERE kind='story' AND status IN ('queued','running')"
                )
            }
            posts = con.execute(
                "SELECT video_id, channel, payload, run_at FROM jobs WHERE kind='post' AND status='queued'"
            ).fetchall()
            for row in posts:
                video_id = row["video_id"]
                channel = row["channel"]
                if not video_id or channel not in ARCHIVE or video_id in active:
                    continue
                try:
                    incoming = json.loads(row["payload"] or "{}")
                except json.JSONDecodeError:
                    incoming = {}
                title = str(incoming.get("title") or video_id)[:180]
                link = incoming.get("link") or ("https://www.youtube.com/watch?v=" + video_id)
                payload = {
                    "videoId": video_id,
                    "title": title,
                    "link": link,
                    "start": "auto",
                    "seconds": 30,
                    "hook": STORY_COPY[channel]["hook"],
                    "cta": STORY_COPY[channel]["cta"],
                    "archive": True,
                }
                con.execute(
                    "INSERT INTO videos (video_id, channel, title, updated_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(video_id) DO UPDATE SET channel=excluded.channel, title=excluded.title, updated_at=excluded.updated_at",
                    (video_id, channel, title, now),
                )
                con.execute(
                    "INSERT INTO jobs (video_id, channel, kind, payload, run_at, priority, status, request_id, created_at) "
                    "VALUES (?, ?, 'story', ?, ?, 2, 'queued', ?, ?)",
                    (
                        video_id, channel, json.dumps(payload, ensure_ascii=False),
                        row["run_at"], "story-" + video_id, now,
                    ),
                )
                active.add(video_id)
                created.append({"channel": channel, "videoId": video_id, "runAt": row["run_at"]})
            con.commit()
        finally:
            con.close()
    set_setting("story_archive_filled", "1")
    return {
        "queued": len(created),
        "music": sum(1 for item in created if item["channel"] == "mrbonzomusic"),
        "beats": sum(1 for item in created if item["channel"] == "mrbonzobeats"),
    }


def _job_view(row, titles):
    payload = {}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    kind = row["kind"]
    status = row["status"]
    labels = {
        "done": ("Στάλθηκε", "ok"),
        "queued": ("Στην ουρά", "warn"),
        "running": ("Τρέχει", "warn"),
        "error": ("Απέτυχε", "bad"),
    }
    label, tone = labels.get(status, (status, ""))
    channel = row["channel"]
    title = payload.get("title") or titles.get(row["video_id"]) or row["video_id"]
    if kind == "short" and payload.get("shortTitle"):
        title = payload.get("shortTitle")
    caption = ""
    if kind == "post":
        caption = str(payload.get("message") or "").split("\n", 1)[0][:180]
    elif kind == "story":
        caption = "Story · %ss" % (payload.get("seconds") or 30)
    return {
        "id": row["id"],
        "videoId": row["video_id"],
        "title": title,
        "caption": caption,
        "channel": channel,
        "channelLabel": (CHANNELS.get(channel) or {}).get("label") or channel,
        "kind": kind,
        "kindLabel": {"short": "Short", "story": "Story"}.get(kind, "Post"),
        "status": status,
        "statusLabel": label,
        "tone": tone,
        "error": row["error"] or "",
        "when": row["finished_at"] or row["started_at"] or row["run_at"] or "",
        "runAt": row["run_at"] or "",
        "platforms": payload.get("platforms") or [],
        "progress": job_progress_pct(row),
        "stage": job_stage_label(row),
        "etaLabel": job_eta_label(row),
        "etaSeconds": job_eta_seconds(row),
    }


def job_lists():
    with DBLOCK:
        con = db()
        pending = con.execute(
            "SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY priority ASC, run_at ASC, id ASC"
        ).fetchall()
        done = con.execute(
            "SELECT * FROM jobs WHERE status IN ('done','error') ORDER BY id DESC LIMIT 200"
        ).fetchall()
        ids = tuple({row["video_id"] for row in list(pending) + list(done)})
        titles = {}
        if ids:
            marks = ",".join("?" for _ in ids)
            for item in con.execute(
                "SELECT video_id, title FROM videos WHERE video_id IN (%s)" % marks, ids
            ):
                titles[item["video_id"]] = item["title"]
        con.close()
    return [_job_view(row, titles) for row in pending], [_job_view(row, titles) for row in done]


def cancel_job(job_id):
    with DBLOCK:
        con = db()
        cur = con.execute("UPDATE jobs SET status='error', error='Ακυρώθηκε', finished_at=? WHERE id=? AND status='queued'", (iso(utcnow()), job_id))
        con.commit()
        changed = cur.rowcount
        con.close()
    if not changed:
        raise ValueError("Μπορεί να ακυρωθεί μόνο ό,τι είναι ακόμα στην ουρά.")


def fire_webhook(spec, payload, request_id):
    body = dict(payload)
    body["requestId"] = request_id
    req = urllib.request.Request(
        N8N + "/webhook/" + spec["path"],
        data=json.dumps(body).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    if WEBHOOK_SECRET:
        req.add_header(HEADER, WEBHOOK_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400]
        raise RuntimeError("Webhook %s: %s" % (err.code, detail)) from err


def execution_nodes(detail):
    data = detail.get("data") if isinstance(detail, dict) else None
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return set()
    if not isinstance(data, dict):
        return set()
    result = data.get("resultData") or {}
    if not result and isinstance(data.get("data"), dict):
        result = data["data"].get("resultData") or {}
    run = result.get("runData") or {}
    return set(run.keys()) if isinstance(run, dict) else set()


def execution_error(detail):
    data = detail.get("data") if isinstance(detail, dict) else None
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = None
    result = data.get("resultData") if isinstance(data, dict) else None
    err = (result or {}).get("error") if isinstance(result, dict) else None
    if isinstance(err, dict) and err.get("message"):
        return str(err["message"])[:500]
    return ""


def execution_state(detail):
    status = (detail or {}).get("status")
    if status:
        return status
    if detail.get("finished"):
        return "success"
    return "running"


def _row_get(row, key, default=None):
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        if key in row.keys():
            val = row[key]
            return default if val is None else val
    except Exception:
        return default
    return default


SHORT_STAGES = (
    ("Manual short", "Ξεκίνημα", 4),
    ("Format", "Προετοιμασία", 6),
    ("Check Short", "Έλεγχος βίντεο", 10),
    ("Pack", "Προετοιμασία", 4),
    ("Only long", "Έλεγχος", 3),
    ("Settings", "Ρυθμίσεις", 3),
    ("Skip wait", "Ρυθμίσεις", 2),
    ("Wait days", "Αναμονή", 4),
    ("Make Short clip", "Κατέβασμα και κόψιμο κλιπ", 200),
    ("Read Short file", "Διάβασμα κλιπ", 8),
    ("Upload R2", "Ανέβασμα αρχείου", 28),
    ("Buffer YouTube", "Ανέβασμα στο YouTube", 50),
    ("Wait Buffer", "Επιβεβαίωση Buffer", 22),
    ("Delete R2", "Καθαρισμός", 6),
    ("Cleanup", "Καθαρισμός", 6),
    ("Check Buffer", "Ολοκλήρωση", 4),
)

STORY_STAGES = (
    ("Manual story", "Ξεκίνημα", 4),
    ("Manual normalize", "Προετοιμασία", 4),
    ("Make story clip", "Κατέβασμα και κόψιμο κλιπ", 200),
    ("Read story file", "Διάβασμα κλιπ", 8),
    ("Upload story", "Ανέβασμα αρχείου", 28),
    ("IG story", "Instagram story", 40),
    ("FB story", "Facebook story", 30),
    ("Story check", "Ολοκλήρωση", 4),
)

POST_STAGES = (
    ("Manual post", "Ξεκίνημα", 4),
    ("Format", "Προετοιμασία", 6),
    ("Check Short", "Έλεγχος", 8),
    ("Pack", "Προετοιμασία", 4),
    ("If Short", "Έλεγχος", 3),
    ("Facebook Purple|Facebook Mr", "Facebook", 16),
    ("Merge Facebook", "Facebook", 4),
    ("Check Facebook", "Facebook", 4),
    ("IG Prep", "Instagram", 4),
    ("Download transcode", "Φτιάχνω reel", 90),
    ("Read reel", "Διάβασμα reel", 6),
    ("Upload R2", "Ανέβασμα αρχείου", 25),
    ("Instagram create", "Instagram", 12),
    ("Wait IG|IG poll|If IG", "Αναμονή Instagram", 50),
    ("Instagram publish", "Δημοσίευση Instagram", 12),
    ("Buffer TikTok", "TikTok", 22),
    ("Wait Buffer", "Επιβεβαίωση Buffer", 20),
    ("Join IG Buffer", "Ολοκλήρωση", 5),
    ("Delete R2", "Καθαρισμός", 6),
    ("Cleanup", "Καθαρισμός", 5),
)


def execution_run_data(detail):
    data = detail.get("data") if isinstance(detail, dict) else None
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {}
    if not isinstance(data, dict):
        return {}
    result = data.get("resultData") or {}
    if not result and isinstance(data.get("data"), dict):
        result = data["data"].get("resultData") or {}
    run = result.get("runData") or {}
    return run if isinstance(run, dict) else {}


def execution_wait_till(detail):
    for key in ("waitTill", "waitTillDate"):
        parsed = parse_iso(detail.get(key) if isinstance(detail, dict) else None)
        if parsed:
            return parsed
    return None


def _node_entry(run, needle):
    hits = []
    parts = [part.strip().lower() for part in (needle or "").split("|") if part.strip()]
    for key, val in (run or {}).items():
        name = (key or "").lower()
        if name.startswith("gate "):
            continue
        if not any(part in name for part in parts):
            continue
        if isinstance(val, list) and val:
            hits.append((key, val[-1]))
    if not hits:
        return None, None
    for key, entry in reversed(hits):
        if _entry_running(entry):
            return key, entry
    undone = [(key, entry) for key, entry in hits if not _entry_done(entry)]
    if undone:
        return undone[-1]
    return hits[-1]


def _entry_running(entry):
    if not entry:
        return False
    st = str(entry.get("executionStatus") or "").lower()
    if st in ("running", "waiting", "new"):
        return True
    if st in ("success", "error", "crashed", "canceled"):
        return False
    return not entry.get("executionTime")


def _entry_done(entry):
    if not entry:
        return False
    st = str(entry.get("executionStatus") or "").lower()
    if st in ("success", "error", "crashed", "canceled"):
        return True
    return bool(entry.get("executionTime")) and st not in ("running", "waiting")


def format_eta(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(seconds))
    if seconds < 20:
        return "σχεδόν έτοιμο"
    if seconds < 60:
        return "ακόμα λιγότερο από 1′"
    minutes = int(round(seconds / 60.0))
    if minutes < 60:
        return "ακόμα ~%d′" % max(1, minutes)
    hours, minutes = divmod(minutes, 60)
    if minutes == 0:
        return "ακόμα ~%dώ" % hours
    return "ακόμα ~%dώ %d′" % (hours, minutes)


def job_progress_pct(row):
    status = _row_get(row, "status")
    if status == "done":
        return 100
    if status == "queued":
        return 0
    try:
        pct = float(_row_get(row, "progress") or 0)
    except (TypeError, ValueError):
        pct = 0
    return max(0, min(99, int(round(pct))))


def job_stage_label(row):
    status = _row_get(row, "status")
    if status == "queued":
        return "Στην ουρά"
    if status == "done":
        return "Ολοκληρώθηκε"
    return (_row_get(row, "stage") or "Σε εξέλιξη") or "Σε εξέλιξη"


def job_eta_seconds(row):
    status = _row_get(row, "status")
    if status == "queued":
        run_at = parse_iso(_row_get(row, "run_at"))
        if run_at:
            return max(0, int((run_at - utcnow()).total_seconds()))
        return None
    if status != "running":
        return None
    eta = parse_iso(_row_get(row, "eta_at"))
    if not eta:
        return None
    return max(0, int((eta - utcnow()).total_seconds()))


def job_eta_label(row):
    return format_eta(job_eta_seconds(row))


def remember_duration(kind, seconds):
    if not seconds or seconds < 8 or seconds > 7200:
        return
    key = "avg_total_" + kind
    try:
        prev = float(setting(key, "0") or 0)
    except (TypeError, ValueError):
        prev = 0
    nxt = seconds if prev <= 0 else prev * 0.65 + seconds * 0.35
    set_setting(key, str(int(nxt)))


def estimate_from_detail(job, detail):
    kind = job.get("kind") or "post"
    stages = {"short": SHORT_STAGES, "story": STORY_STAGES}.get(kind, POST_STAGES)
    run = execution_run_data(detail) if detail else {}
    wait_till = execution_wait_till(detail) if detail else None
    weights = [max(1, int(item[2])) for item in stages]
    total = float(sum(weights))
    try:
        learned = float(setting("avg_total_" + kind, "0") or 0)
    except (TypeError, ValueError):
        learned = 0
    scale = (learned / total) if learned >= 20 else 1.0
    current_i = 0
    current_name = stages[0][1]
    frac = 0.0
    started = parse_iso(job.get("started_at"))
    elapsed = (utcnow() - started).total_seconds() if started else 0
    if not run:
        pct = min(8, 2 + elapsed / 8.0)
        remain = max(30, (learned or 240) - elapsed)
        return pct, "Ξεκίνημα", remain
    def later_started(index):
        for needle2, _label2, _typ in stages[index + 1 :]:
            _k2, later = _node_entry(run, needle2)
            if later:
                return True
        return False

    for i, (needle, label, typical) in enumerate(stages):
        _key, entry = _node_entry(run, needle)
        if _entry_done(entry) or (not entry and later_started(i)):
            current_i = i + 1
            continue
        current_i = i
        current_name = label
        if wait_till and "αναμον" in label.lower():
            remain_wait = max(0, (wait_till - utcnow()).total_seconds())
            window = max(remain_wait + 1, typical * scale)
            frac = max(0.0, min(0.92, 1.0 - remain_wait / window))
        elif _entry_running(entry) or entry:
            node_start = parse_iso(entry.get("startTime") if isinstance(entry, dict) else None)
            node_elapsed = (utcnow() - node_start).total_seconds() if node_start else elapsed
            frac = max(0.05, min(0.92, node_elapsed / max(typical * scale, 8)))
        else:
            frac = 0.0
        break
    else:
        current_i = len(stages)
        current_name = "Ολοκλήρωση"
        frac = 1.0
    done_w = sum(weights[:current_i]) + weights[min(current_i, len(weights) - 1)] * frac if stages else 0
    pct = min(97, max(3, 100.0 * done_w / total)) if current_i < len(stages) else 97
    remain_w = total - done_w
    remain = remain_w * scale
    if wait_till:
        remain = max(remain, (wait_till - utcnow()).total_seconds())
    remain = max(8, remain)
    return pct, current_name, remain


def save_job_progress(job_id, pct, stage, remain):
    eta = iso(utcnow() + timedelta(seconds=max(0, int(remain or 0)))) if remain is not None else None
    with DBLOCK:
        con = db()
        con.execute(
            "UPDATE jobs SET progress=?, stage=?, eta_at=? WHERE id=?",
            (float(pct or 0), stage or "", eta, job_id),
        )
        con.commit()
        con.close()


def find_execution(workflow_id, request_id, started_after):
    wid = urllib.parse.quote(str(workflow_id))
    items = []
    seen = set()
    for status in ("running", "waiting", "new", "success", "error", "canceled"):
        listing = n8n_request("GET", "/api/v1/executions?status=%s&workflowId=%s&limit=8" % (status, wid))
        batch = listing.get("data") if isinstance(listing, dict) else listing
        for item in batch or []:
            item_id = item.get("id")
            if item_id in seen:
                continue
            seen.add(item_id)
            items.append(item)
    floor = parse_iso(started_after)
    recent = []
    for item in items:
        started = parse_iso(item.get("startedAt"))
        if floor and started and started < floor - timedelta(seconds=15):
            continue
        recent.append(item)
    fallback = None
    for item in recent:
        detail = unwrap_execution(n8n_request("GET", "/api/v1/executions/%s?includeData=true" % item["id"]))
        detail["id"] = detail.get("id") or item["id"]
        if request_id and request_id in json.dumps(detail, default=str):
            return detail
        fallback = detail
    if len(recent) == 1:
        return fallback
    return None


def finish_job(job, status, error="", execution_id=""):
    kind = job["kind"]
    column, err_col, exec_col, at_col, done_word = KIND_FIELDS.get(kind) or KIND_FIELDS["post"]
    video_status = {"done": done_word, "error": "error"}.get(status, status)
    with DBLOCK:
        con = db()
        done_pct = 100 if status == "done" else (_row_get(job, "progress") or 0)
        done_stage = "Ολοκληρώθηκε" if status == "done" else (_row_get(job, "stage") or "")
        con.execute(
            "UPDATE jobs SET status=?, error=?, execution_id=?, finished_at=?, progress=?, stage=?, eta_at=? WHERE id=?",
            (
                status, error, execution_id or job["execution_id"],
                iso(utcnow()) if status in ("done", "error") else None,
                done_pct, done_stage, None, job["id"],
            ),
        )
        sets = ["%s=?" % column, "%s=?" % err_col, "updated_at=?"]
        args = [video_status, error, iso(utcnow())]
        if execution_id:
            sets.append("%s=?" % exec_col)
            args.append(execution_id)
        if status == "done":
            sets.append("%s=?" % at_col)
            args.append(iso(utcnow()))
        args.append(job["video_id"])
        con.execute("UPDATE videos SET %s WHERE video_id=?" % ", ".join(sets), args)
        con.commit()
        con.close()
    if kind == "story" and status == "done":
        eid = execution_id or job.get("execution_id") or ""
        if eid and API_KEY:
            try:
                detail = unwrap_execution(n8n_request("GET", "/api/v1/executions/%s?includeData=true" % eid, timeout=60))
                harvest_publications(detail, eid)
            except Exception:
                traceback.print_exc()


def poll_job(job):
    started = parse_iso(job["started_at"])
    if started and utcnow() - started > timedelta(hours=2):
        finish_job(job, "error", "Η εκτέλεση ξεπέρασε τις 2 ώρες.", job["execution_id"] or "")
        return
    name, _spec = spec_for(job["channel"], job["kind"])
    try:
        meta = published_copy(name) or {}
    except RuntimeError:
        refresh_workflow_index()
        meta = published_copy(name) or {}
    if not meta.get("id"):
        refresh_workflow_index()
        meta = published_copy(name) or {}
    detail = None
    if job["execution_id"]:
        detail = unwrap_execution(n8n_request("GET", "/api/v1/executions/%s?includeData=true" % job["execution_id"]))
    elif meta.get("id"):
        detail = find_execution(meta["id"], job["request_id"], job["started_at"])
    if not detail:
        if started and utcnow() - started > timedelta(minutes=12):
            finish_job(job, "error", "Δεν βρέθηκε εκτέλεση στο n8n. Έλεγξε ότι το workflow είναι ενεργό.")
            return
        try:
            pct, stage, remain = estimate_from_detail(job, {})
            save_job_progress(job["id"], pct, stage, remain)
        except Exception:
            traceback.print_exc()
        return
    execution_id = str(detail.get("id") or job["execution_id"] or "")
    if execution_id and execution_id != (job["execution_id"] or ""):
        with DBLOCK:
            con = db()
            con.execute("UPDATE jobs SET execution_id=? WHERE id=?", (execution_id, job["id"]))
            con.commit()
            con.close()
        job["execution_id"] = execution_id
    state = execution_state(detail)
    if state in ("running", "waiting", "new", "unknown"):
        try:
            pct, stage, remain = estimate_from_detail(job, detail)
            save_job_progress(job["id"], pct, stage, remain)
        except Exception:
            traceback.print_exc()
        return
    if state == "success":
        if job["kind"] == "short":
            nodes = execution_nodes(detail)
            if nodes and "Make Short clip" not in nodes:
                finish_job(job, "error", "Το βίντεο είναι ήδη Short, οπότε δεν κόπηκε νέο κλιπ.", execution_id)
                return
        if job["kind"] == "story":
            nodes = execution_nodes(detail)
            if nodes and "Make story clip" not in nodes:
                finish_job(job, "error", "Δεν κόπηκε απόσπασμα.", execution_id)
                return
            if nodes and "Story check" not in nodes:
                finish_job(job, "error", "Το story δεν ολοκλήρωσε το ανέβασμα.", execution_id)
                return
        started = parse_iso(job.get("started_at"))
        if started:
            remember_duration(job["kind"], (utcnow() - started).total_seconds())
        finish_job(job, "done", "", execution_id)
        return
    finish_job(job, "error", execution_error(detail) or state, execution_id)


def start_job(job):
    name, spec = spec_for(job["channel"], job["kind"])
    meta = {}
    if not API_KEY:
        finish_job(job, "error", "Λείπει το N8N_API_KEY.")
        return
    try:
        refresh_workflow_index()
        meta = published_copy(name) or {}
    except Exception as err:
        finish_job(job, "error", str(err))
        return
    if not meta.get("active"):
        finish_job(job, "error", "Το workflow «%s» δεν είναι ενεργό. Πάτα Ενεργοποίηση." % name)
        return
    started = iso(utcnow())
    with DBLOCK:
        con = db()
        con.execute(
            "UPDATE jobs SET status='running', started_at=?, error='', progress=3, stage=?, eta_at=? WHERE id=?",
            (started, "Ξεκίνημα", iso(utcnow() + timedelta(minutes=4)), job["id"]),
        )
        con.commit()
        con.close()
    job["started_at"] = started
    job["status"] = "running"
    try:
        fire_webhook(spec, json.loads(job["payload"]), job["request_id"])
    except Exception as err:
        finish_job(job, "error", str(err))


def tick():
    if API_KEY:
        with DBLOCK:
            con = db()
            running = [dict(row) for row in con.execute("SELECT * FROM jobs WHERE status='running'").fetchall()]
            con.close()
        for job in running:
            try:
                poll_job(job)
            except Exception:
                traceback.print_exc()
        with DBLOCK:
            con = db()
            still = con.execute("SELECT id FROM jobs WHERE status='running'").fetchone()
            nxt = None if still else con.execute(
                "SELECT * FROM jobs WHERE status='queued' AND run_at<=? ORDER BY priority ASC, run_at ASC, id ASC LIMIT 1",
                (iso(utcnow()),),
            ).fetchone()
            con.close()
        if nxt:
            start_job(dict(nxt))


def worker_loop():
    while True:
        try:
            tick()
        except Exception:
            traceback.print_exc()
        busy = False
        try:
            with DBLOCK:
                con = db()
                busy = bool(con.execute("SELECT id FROM jobs WHERE status='running'").fetchone())
                con.close()
        except Exception:
            busy = False
        time.sleep(4 if busy else 8)


def scrub(text):
    if GITHUB_TOKEN and text:
        return text.replace(GITHUB_TOKEN, "***")
    return text or ""


def git(*args, header=False):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    cmd = ["git", "-c", "safe.directory=" + REPO_DIR]
    if header and GITHUB_TOKEN:
        basic = base64.b64encode(("x-access-token:" + GITHUB_TOKEN).encode("ascii")).decode("ascii")
        cmd.extend(["-c", "http.extraHeader=Authorization: Basic " + basic])
    cmd.extend(args)
    proc = subprocess.run(cmd, cwd=REPO_DIR, env=env, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(scrub((proc.stderr or proc.stdout or "git failed")[-500:]))
    return proc.stdout


def sanitize_workflow(wf):
    clean = {
        "id": wf.get("id"),
        "name": wf.get("name"),
        "active": wf.get("active"),
        "nodes": [],
        "connections": wf.get("connections") or {},
        "settings": wf.get("settings") or {},
    }
    if wf.get("meta"):
        clean["meta"] = wf["meta"]
    for node in wf.get("nodes") or []:
        copy = {key: value for key, value in node.items() if key != "credentials"}
        creds = {}
        for kind, ref in (node.get("credentials") or {}).items():
            if isinstance(ref, dict):
                creds[kind] = {key: ref[key] for key in ("id", "name") if key in ref}
        if creds:
            copy["credentials"] = creds
        clean["nodes"].append(copy)
    return clean


def slug(name):
    out = []
    for char in (name or "workflow").lower():
        if char.isalnum():
            out.append(char)
        elif char in " -_":
            out.append("-")
    text = "".join(out).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return text or "workflow"


def run_backup():
    if not BACKUP_LOCK.acquire(blocking=False):
        return {"ok": False, "message": "Τρέχει ήδη backup."}
    try:
        if not API_KEY:
            raise RuntimeError("Λείπει το N8N_API_KEY.")
        if not GITHUB_REPO or not GITHUB_TOKEN:
            raise RuntimeError("Λείπουν GITHUB_BACKUP_REPO και GITHUB_BACKUP_TOKEN.")
        if GITHUB_REPO.count("/") != 1 or any(ch.isspace() for ch in GITHUB_REPO):
            raise RuntimeError("Το GITHUB_BACKUP_REPO πρέπει να είναι owner/repo.")
        os.makedirs(REPO_DIR, exist_ok=True)
        if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
            git("init", "-b", "main")
        remotes = git("remote")
        origin = "https://github.com/%s.git" % GITHUB_REPO
        if "origin" in remotes.split():
            git("remote", "set-url", "origin", origin)
        else:
            git("remote", "add", "origin", origin)
        wf_dir = os.path.join(REPO_DIR, "workflows")
        os.makedirs(wf_dir, exist_ok=True)
        for old in os.listdir(wf_dir):
            if old.endswith(".json"):
                os.remove(os.path.join(wf_dir, old))
        summaries = list_paged("/api/v1/workflows?limit=100")
        for summary in summaries:
            full = unwrap_workflow(n8n_request("GET", "/api/v1/workflows/%s" % summary["id"]))
            clean = sanitize_workflow(full)
            path = os.path.join(wf_dir, slug(clean.get("name")) + ".json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(clean, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        creds = []
        for item in list_paged("/api/v1/credentials?limit=100"):
            creds.append({key: item.get(key) for key in ("id", "name", "type", "createdAt", "updatedAt")})
        with open(os.path.join(REPO_DIR, "credentials-manifest.json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(creds, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        with open(os.path.join(REPO_DIR, "n8n-version.txt"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("image=%s\nexported=%s\n" % (N8N_IMAGE, iso(utcnow())))
        with open(os.path.join(REPO_DIR, "RESTORE.md"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "# Επαναφορά n8n\n\n"
                "Τα JSON είναι η λογική των workflows. Δεν περιέχουν tokens.\n\n"
                "Για να ξαναδουλέψουν τα OAuth χρειάζεσαι και το `N8N_ENCRYPTION_KEY` από το `.env` "
                "και το volume `n8n_data` από το Duplicati. Χωρίς αυτά, κάνε import τα workflows "
                "και ξανασύνδεσε τα credentials (Buffer, Facebook, S3, header auth του panel).\n"
            )
        git("add", "workflows", "credentials-manifest.json", "n8n-version.txt", "RESTORE.md")
        dirty = git("status", "--porcelain").strip()
        if not dirty:
            message = "Καμία αλλαγή από το προηγούμενο backup."
        else:
            git("-c", "user.name=n8n panel", "-c", "user.email=n8n-panel@homelab.lan",
                "commit", "-m", "Backup n8n workflows %s" % iso(utcnow()))
            git("push", "--quiet", "origin", "HEAD:main", header=True)
            message = "Στάλθηκαν %d workflows στο %s." % (len(summaries), GITHUB_REPO)
        set_setting("backup_at", iso(utcnow()))
        set_setting("backup_ok", "1")
        set_setting("backup_message", message)
        return {"ok": True, "message": message}
    except Exception as err:
        traceback.print_exc()
        set_setting("backup_at", iso(utcnow()))
        set_setting("backup_ok", "0")
        set_setting("backup_message", scrub(str(err)))
        return {"ok": False, "message": scrub(str(err))}
    finally:
        BACKUP_LOCK.release()


def backup_ready():
    return bool(GITHUB_REPO and GITHUB_TOKEN and API_KEY)


def wait_n8n(tries=45, delay=2):
    for _ in range(tries):
        try:
            n8n_request("GET", "/api/v1/workflows?limit=1")
            return True
        except Exception:
            time.sleep(delay)
    return False


def backup_on_start():
    if not backup_ready():
        return
    if not wait_n8n():
        set_setting("backup_at", iso(utcnow()))
        set_setting("backup_ok", "0")
        set_setting("backup_message", "Το n8n δεν ήταν έτοιμο στο άνοιγμα του stack.")
        return
    run_backup()


def backup_loop():
    while True:
        time.sleep(60)
        moment = local_now()
        if moment.hour != 3 or moment.minute < 30:
            continue
        last = setting("backup_day", "")
        today = moment.date().isoformat()
        if last == today or not backup_ready():
            continue
        set_setting("backup_day", today)
        run_backup()


def overview():
    queue, history = job_lists()
    index_error = ""
    if API_KEY:
        try:
            refresh_workflow_index()
        except Exception as err:
            index_error = str(err)
    return {
        "api": bool(API_KEY),
        "github": bool(GITHUB_REPO and GITHUB_TOKEN),
        "githubRepo": GITHUB_REPO,
        "gapHours": gap_hours(),
        "sync": SYNC,
        "indexError": index_error,
        "workflows": workflow_status(),
        "backup": {
            "at": setting("backup_at", ""),
            "ok": setting("backup_ok", ""),
            "message": setting("backup_message", ""),
        },
        "queue": queue,
        "history": history,
        "youtube": youtube_ready(),
    }


def _widget_item(item):
    if not item:
        return None
    return {
        "title": item.get("title") or "",
        "kind": item.get("kindLabel") or "",
        "status": item.get("statusLabel") or "",
        "when": item.get("when") or item.get("runAt") or "",
        "error": item.get("error") or "",
        "progress": item.get("progress") or 0,
        "stage": item.get("stage") or "",
        "eta": item.get("etaLabel") or "",
    }


def widget_summary():
    queue, history = job_lists()
    running = next((item for item in queue if item["status"] == "running"), None)
    waiting = [item for item in queue if item["status"] == "queued"]
    return {
        "queue": len(waiting),
        "running": _widget_item(running),
        "last": _widget_item(history[0] if history else None),
    }


LOGIN = r"""<!doctype html><html lang="el"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>n8n posts · Σύνδεση</title><style>
:root{--bg:#07070e;--fg:#f0eef8;--mut:#9aa0b8;--card:#141422;--bd:rgba(170,160,220,.16);--ac:#7c5cbf;--bad:#e06b6b}
*{box-sizing:border-box}html,body{height:100%}body{font:15px/1.45 system-ui,Segoe UI,sans-serif;background:radial-gradient(1200px 600px at 20% -10%,rgba(124,92,191,.22),transparent 55%),var(--bg);color:var(--fg);margin:0;display:grid;place-items:center}
form{background:linear-gradient(165deg,rgba(88,70,160,.32),rgba(16,18,36,.88));border:1px solid var(--bd);border-radius:16px;padding:28px 24px;width:min(380px,92vw);display:flex;flex-direction:column;gap:10px}
h1{font-size:20px;margin:0}p.sub{margin:0 0 8px;color:var(--mut);font-size:13px}
label{color:var(--mut);font-size:12px;font-weight:600}
input{background:rgba(7,7,14,.65);color:var(--fg);border:1px solid var(--bd);border-radius:10px;padding:11px 12px;font:inherit}
button{background:var(--ac);color:#fff;border:0;border-radius:10px;padding:11px;font:inherit;font-weight:650;cursor:pointer}
.e{color:var(--bad);font-size:13px;margin:0}
</style></head><body><form method="post" action="/login">
<h1>n8n posts</h1><p class="sub">Επιλογή βίντεο και backup workflows</p>%ERR%
<label for="u">Username</label><input id="u" name="username" value="admin" autocomplete="username" required>
<label for="p">Password</label><input id="p" name="password" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Σύνδεση</button></form></body></html>"""

PAGE = r"""<!doctype html><html lang="el"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>n8n posts</title><style>
:root{--bg:#07070e;--fg:#f0eef8;--mut:#9aa0b8;--ac:#7c5cbf;--ok:#5dcc8a;--bad:#e06b6b;--warn:#e6b35c;--bd:rgba(170,160,220,.16)}
*{box-sizing:border-box}body{font:14px/1.45 system-ui,Segoe UI,sans-serif;margin:0;background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;z-index:3;padding:14px 18px;border-bottom:1px solid var(--bd);background:rgba(7,7,14,.92);backdrop-filter:blur(12px)}
.top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}
h1{font-size:18px;margin:0}p.lead{color:var(--mut);margin:4px 0 0;font-size:13px}
.bar,.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
main{padding:16px 18px 48px;display:flex;flex-direction:column;gap:14px}
.note{border:1px solid var(--bd);border-radius:12px;padding:10px 12px;color:var(--mut);background:rgba(20,20,34,.7)}
.note.bad{color:var(--bad);border-color:rgba(224,107,107,.4)}
button,.btn{background:var(--ac);color:#fff;border:0;border-radius:10px;padding:8px 12px;font:inherit;cursor:pointer;font-weight:600}
button.g{background:transparent;color:var(--fg);border:1px solid var(--bd);font-weight:500}
button:disabled{opacity:.45;cursor:not-allowed}
input,textarea,select{background:rgba(20,20,34,.9);color:var(--fg);border:1px solid var(--bd);border-radius:10px;padding:8px 10px;font:inherit;width:100%}
input[type=date],input[type=time]{color-scheme:dark}
input[type=checkbox]{width:auto;padding:0}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:transparent;color:var(--mut);border:1px solid var(--bd);border-radius:999px;padding:6px 11px;cursor:pointer}
.chip.on{color:#fff;background:rgba(124,92,191,.35);border-color:rgba(124,92,191,.7)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{position:relative;display:flex;gap:10px;border:1px solid var(--bd);border-radius:12px;padding:10px;background:linear-gradient(165deg,rgba(88,70,160,.22),rgba(12,12,22,.92))}
.card.done-one::before,.card.done-both::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:3px}
.card.done-both::before{background:var(--ok)}
.card.done-one::before{background:linear-gradient(var(--ok) 50%, rgba(170,160,220,.28) 50%)}
.card > img{width:120px;height:68px;object-fit:cover;border-radius:8px;background:#111;flex:none}
.card h2{font-size:14px;margin:0 0 4px}
.meta{color:var(--mut);font-size:12px}
.badge{display:inline-block;border-radius:999px;padding:1px 7px;font-size:11px;border:1px solid var(--bd);margin-right:4px}
.badge.ok{color:var(--ok);border-color:rgba(93,204,138,.45)}
.badge.warn{color:var(--warn);border-color:rgba(230,179,92,.45)}
.badge.bad{color:var(--bad);border-color:rgba(224,107,107,.45)}
dialog{border:1px solid var(--bd);border-radius:16px;background:#12121c;color:var(--fg);width:min(520px,94vw);padding:16px}
#story-preview{margin:8px 0 0;padding:16px 12px;border-radius:12px;background:#0c0c14;text-align:center;white-space:pre-line;font-weight:700;letter-spacing:.03em;line-height:1.45}
dialog::backdrop{background:rgba(0,0,0,.55)}
#pairs{width:min(640px,94vw)}
.delopts{display:flex;flex-direction:column;gap:8px;margin-top:8px}
.delopts label{display:flex;gap:8px;align-items:flex-start;color:var(--fg);margin:0}
#pair-list,#pair-hidden{display:flex;flex-direction:column;gap:8px;margin-top:8px;max-height:42vh;overflow:auto}
.pair{border:1px solid var(--bd);border-radius:10px;padding:8px}
.grow{flex:1;min-width:0}
a{color:#c4b5fd}
label{display:block;color:var(--mut);font-size:12px;margin:8px 0 4px}
.checks{display:flex;gap:12px;flex-wrap:wrap}.checks label{display:flex;align-items:center;gap:6px;width:auto;color:var(--fg);margin:0}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--bd);vertical-align:top}
section h3{margin:0 0 8px;font-size:15px}
button.big{padding:10px 16px;min-width:92px}
button.st-done{background:transparent;color:var(--ok);border:1px solid rgba(93,204,138,.75);font-weight:600}
button.st-run{background:transparent;color:var(--warn);border:1px solid rgba(230,179,92,.8);font-weight:600}
button.st-bad{background:transparent;color:var(--bad);border:1px solid rgba(224,107,107,.8);font-weight:600}
details{margin-top:10px}details summary{cursor:pointer;color:var(--mut);font-weight:600}
#view-videos[hidden],#view-history[hidden],#view-pages[hidden],#view-posts[hidden]{display:none}
.tabs{display:flex;width:fit-content;max-width:100%;margin-top:12px;border:1px solid var(--bd);border-radius:12px;overflow:hidden}
.tabs button{background:transparent;color:var(--mut);border:0;border-right:1px solid var(--bd);border-radius:0;padding:8px 16px;font-weight:600}
.tabs button:last-child{border-right:0}
.tabs button.on{background:rgba(124,92,191,.35);color:#fff}
.subtabs{display:flex;flex-wrap:wrap;gap:2px 4px;margin-top:8px}
.subtabs[hidden]{display:none}
button.sub{background:transparent;color:var(--mut);border:0;border-bottom:2px solid transparent;border-radius:0;padding:6px 10px;font-weight:600}
button.sub.on{color:#fff;border-bottom-color:#7c5cbf}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.toolbar input[type=search]{flex:1 1 220px;width:auto;min-width:0}
.qbar{display:flex;flex-direction:column;gap:8px;margin-top:10px;max-height:280px;overflow:auto}
.qbar:empty{display:none}
.when{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.when label{margin:0}
.qitem{display:flex;flex-wrap:wrap;gap:8px;align-items:center;border:1px solid var(--bd);border-radius:12px;padding:8px 10px;background:rgba(20,20,34,.7)}
.qitem .grow{flex:1;min-width:180px}
.qthumb{width:96px;height:54px;object-fit:cover;border-radius:8px;background:#111;flex:none}
.qitem .pbar-wrap{margin:4px 0 0}
.camp{display:block;padding:14px}
.camp h3{margin:0 0 6px}
button.sched-line{background:transparent;color:var(--fg);border:1px dashed var(--bd);border-radius:10px;padding:8px 12px;font-weight:600}
.sched-edit[hidden]{display:none}
.sched-edit label{width:auto;margin:0}
.sched-edit select,.sched-edit input{width:auto}
.camp-grid{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.camp-page{display:grid;grid-template-columns:minmax(0,1fr) minmax(180px,240px);gap:10px;align-items:start;border-top:1px solid var(--bd);padding-top:12px}
.camp-page textarea{min-height:120px}
.page-head{display:flex;gap:8px;align-items:center;justify-content:space-between;color:var(--fg);font-size:13px;margin-bottom:4px}
.page-head select{width:auto;max-width:52%}
.preview{border:1px solid var(--bd);border-radius:10px;background:#0c0c16;overflow:hidden}
.preview p{margin:0;padding:8px 10px 6px;font-size:13px}
.preview img{width:100%;height:110px;object-fit:cover;display:block;background:#111}
.preview .meta{padding:6px 10px 8px}
.imgprev{display:block;width:min(220px,100%);height:auto;max-height:120px;object-fit:cover;border-radius:8px;margin-top:6px;background:#111}
.imgprev[hidden],.preview img[hidden]{display:none}
.pbar-wrap{margin:6px 0 2px}
.pbar-meta{color:var(--mut);font-size:11px;margin-bottom:4px}
.pbar{height:7px;border-radius:999px;background:rgba(170,160,220,.16);overflow:hidden}
.pbar i{display:block;height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,#7c5cbf,#9b7eef);transition:width .4s ease}
@media(max-width:720px){.camp-page{grid-template-columns:1fr}}
</style></head><body>
<header><div class="top"><div><h1>n8n posts</h1><p class="lead">YouTube posts/shorts και εβδομαδιαία Facebook (Official site, BaseBox).</p></div>
<div class="bar"><button class="g" id="openset" type="button">Ρυθμίσεις</button><a class="btn g" href="/logout">Έξοδος</a></div></div>
<div class="tabs" id="tabs">
<button type="button" class="on" data-tab="channels">Κανάλια</button>
<button type="button" data-tab="posts">Ουρά</button>
<button type="button" data-tab="pages">Σελίδες</button>
<button type="button" data-tab="history">Ιστορικό</button>
</div>
<div class="subtabs" id="subtabs"></div>
</header>
<main>
<div id="banner"></div>
<section id="view-videos">
<div class="toolbar">
<input id="q" type="search" placeholder="Φίλτρο στους τίτλους αυτού του καναλιού">
<button class="g" id="refresh" type="button">Ανανέωση λίστας</button>
<button class="g" id="archive" type="button">Αρχείο shorts</button>
<button class="g" id="pairs-open" type="button">Ζεύγη</button>
</div>
<div class="chips" id="vfilters" style="margin-top:8px">
<button type="button" class="chip on" data-vf="all">Όλα</button>
<button type="button" class="chip" data-vf="nopost">χωρίς post</button>
<button type="button" class="chip" data-vf="noshort">χωρίς short</button>
<button type="button" class="chip" data-vf="queued">στην ουρά</button>
<button type="button" class="chip" data-vf="error">απέτυχε</button>
</div>
<p class="meta" id="count" style="margin:8px 0 0"></p>
<button type="button" class="g" id="queuesum" style="margin-top:8px">Ουρά</button>
<div class="grid" id="grid" style="margin-top:12px"></div>
</section>
<section id="view-posts" hidden>
<p class="meta" style="margin:0 0 8px">Ό,τι περιμένει. Η ακύρωση βγάζει μόνο αυτή τη γραμμή. Το άλλο είδος του ίδιου βίντεο μένει.</p>
<p class="meta" id="postsum" style="margin:0 0 8px"></p>
<div class="chips" id="qfilters" style="margin-bottom:8px">
<button type="button" class="chip on" data-qf="all">Όλα</button>
<button type="button" class="chip" data-qf="post">Posts</button>
<button type="button" class="chip" data-qf="short">Shorts</button>
<button type="button" class="chip" data-qf="story">Stories</button>
</div>
<div class="qbar" id="postqueue" style="max-height:none"></div>
</section>
<section id="view-pages" hidden>
<p class="meta" style="margin:0 0 10px">Πότε και τι ποστάρει το Official site και το BaseBox στο Facebook. Αποθήκευση ενημερώνει το n8n. Δημοσίευση τώρα στέλνει στις τσεκαρισμένες σελίδες.</p>
<div id="campaigns"></div>
</section>
<section id="view-history" hidden>
<div class="chips" id="hchannels" style="margin-bottom:8px"></div>
<div class="chips" id="hfilters">
<button type="button" class="chip on" data-hf="all">Όλα</button>
<button type="button" class="chip" data-hf="post">Posts</button>
<button type="button" class="chip" data-hf="short">Shorts</button>
<button type="button" class="chip" data-hf="story">Stories</button>
<button type="button" class="chip" data-hf="error">Αποτυχίες</button>
</div>
<div id="history" style="margin-top:12px"></div>
</section>
</main>
<dialog id="dlg"><form id="form">
<h3 id="dlg-title" style="margin:0"></h3>
<p class="meta" id="dlg-video" style="margin:4px 0 8px"></p>
<p class="meta" id="dlg-note" style="margin:0 0 8px"></p>
<div id="post-fields">
<label>Κείμενο</label><textarea id="message" rows="6"></textarea>
<div class="checks"><label><input type="checkbox" name="platforms" value="facebook" checked> Facebook</label>
<label><input type="checkbox" name="platforms" value="instagram" checked> Instagram</label>
<label><input type="checkbox" name="platforms" value="tiktok" checked> TikTok</label></div>
</div>
<div id="short-fields">
<label>Τίτλος Short</label><input id="shortTitle">
<label>Περιγραφή</label><textarea id="shortDescription" rows="4"></textarea>
<label>Κείμενο πάνω</label><input id="hook">
<label>Κείμενο κάτω</label><input id="cta">
<details id="more"><summary>Περισσότερα</summary>
<label>Αρχή (auto ή δευτερόλεπτα)</label><input id="start" value="auto">
<label>Δευτερόλεπτα (5–170)</label><input id="seconds" type="number" min="5" max="170" value="30">
</details>
</div>
<div id="story-fields">
<label>Αρχή (auto ή δευτερόλεπτα)</label><input id="storyStart" value="auto">
<label>Δευτερόλεπτα (5–60)</label><input id="storySeconds" type="number" min="5" max="60" value="30">
<label>Κείμενο πάνω</label><input id="storyHook">
<label>Κείμενο κάτω</label><input id="storyCta">
<div id="story-preview"></div>
</div>
<div class="when">
<label>Ημερομηνία<input id="runDate" type="date"></label>
<label>Ώρα<input id="runTime" type="time"></label>
</div>
<div class="row" style="margin-top:12px"><button type="submit" data-when="now">Στείλε το</button><button class="g" type="submit" data-when="at">Προγραμμάτισε</button><button class="g" type="submit" data-when="queue">Βάλ’ το στην ουρά</button><button class="g" type="button" id="close">Κλείσιμο</button></div>
</form></dialog>
<dialog id="settings">
<h3 style="margin:0 0 8px">Ρυθμίσεις</h3>
<label>Κενό ουράς (ώρες)</label>
<div class="row"><input id="gap" type="number" min="1" max="168" style="width:90px"><button class="g" id="savegap" type="button">Αποθήκευση</button></div>
<p class="meta" id="syncmsg"></p>
<div class="row" style="margin-top:8px"><button id="dosync" type="button">Sync webhooks</button><button id="backup" class="g" type="button">Backup τώρα</button></div>
<p class="meta" id="backupmsg"></p>
<p class="meta" id="githubnote"></p>
<p class="meta" id="ytnote"></p>
<div class="row" style="margin-top:12px"><button class="g" type="button" id="closeset">Κλείσιμο</button></div>
</dialog>
<dialog id="pairs">
<h3 style="margin:0">Ζεύγη shorts</h3>
<p class="meta">Αμφίβολα και από τα δύο κανάλια. Η σύνδεση κρύβει το short από τη λίστα και το δείχνει στο long.</p>
<div id="pair-list"></div>
<h3 style="margin:14px 0 0;font-size:15px">Χειροκίνητα</h3>
<label for="pair-source">Long βίντεο (id ή URL)</label>
<input id="pair-source" placeholder="id του long">
<label for="pair-url">Short (URL)</label>
<input id="pair-url" placeholder="https://www.youtube.com/shorts/…">
<div class="row" style="margin-top:8px"><button type="button" id="pair-manual">Σύνδεση</button></div>
<h3 style="margin:14px 0 0;font-size:15px">Κρυμμένα</h3>
<div id="pair-hidden"></div>
<div class="row" style="margin-top:12px"><button class="g" type="button" id="pair-close">Κλείσιμο</button></div>
</dialog>
<dialog id="del">
<h3 style="margin:0">Διαγραφή</h3>
<p class="meta" id="del-title" style="margin:4px 0 0"></p>
<div id="del-body" class="delopts"></div>
<div class="row" style="margin-top:12px"><button type="button" id="del-go">Εφαρμογή</button><button class="g" type="button" id="del-close">Κλείσιμο</button></div>
</dialog>
<script>
const $ = s => document.querySelector(s[0]==='#'||s[0]==='.'||s[0]==='[' ? s : '#'+s);
const channels = [
  {id:'mrbonzomusic', label:'Mr. Bonzo Music'},
  {id:'mrbonzobeats', label:'Mr. Bonzo Beats'}
];
let channel = 'mrbonzomusic';
let videos = [];
let queue = [];
let history = [];
let tab = '';
let qfilter = 'all';
let qchannel = 'all';
let hfilter = 'all';
let hchannel = 'all';
let vfilter = 'all';
let campaignId = 'official';
let campaignPayload = null;
let campSnap = '';
let current = null;
let currentDelete = null;
let kind = 'post';
let canSend = false;
function side(v, which){
  if (which==='story') return {st:v.storyStatus||'', id:v.storyJobId, at:v.storyRunAt, prog:v.storyProgress, stage:v.storyStage, eta:v.storyEta, err:v.storyError};
  if (which==='short') return {st:v.shortStatus||'', id:v.shortJobId, at:v.shortRunAt, prog:v.shortProgress, stage:v.shortStage, eta:v.shortEta, err:v.shortError};
  return {st:v.postStatus||'', id:v.postJobId, at:v.postRunAt, prog:v.postProgress, stage:v.postStage, eta:v.postEta, err:v.postError};
}
function actState(v, which){
  const st = side(v, which).st;
  if (st==='running' || st==='queued') return 'run';
  if (st==='error') return 'bad';
  if (which==='post' && st==='posted') return 'done';
  if (which==='short' && (st==='shorted' || v.nativeShort)) return 'done';
  if (which==='story' && st==='storied') return 'done';
  return '';
}
function actLabel(v, which){
  const state = actState(v, which);
  if (which==='post') return state==='done' ? 'Post ✓' : 'Post';
  if (which==='story') return state==='done' ? 'Story ✓' : 'Story';
  if (state==='done' && v.shortStatus==='shorted') return 'Short ✓';
  if (state==='done') return 'Είναι short ✓';
  return 'Short';
}
function actAria(v, which){
  const state = actState(v, which);
  const name = which==='post' ? 'Post' : (which==='story' ? 'Story' : 'Short');
  if (state==='run') return name + ', στην ουρά ή τρέχει';
  if (state==='bad') return name + ', απέτυχε';
  if (state==='done' && which==='short' && v.shortStatus!=='shorted') return 'Είναι ήδη short';
  if (state==='done') return name + ', ήδη δημοσιευμένο';
  return name;
}
function cardMark(v){
  const post = actState(v,'post')==='done';
  const short = actState(v,'short')==='done';
  if (post && short) return ' done-both';
  if (post || short) return ' done-one';
  return '';
}
const dur = n => {
  if (n == null) return '';
  n = Math.round(n); const h = Math.floor(n/3600), m = Math.floor((n%3600)/60), s = n%60;
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${m}:${String(s).padStart(2,'0')}`;
};
const when = ts => ts ? new Date(ts*1000).toLocaleDateString('el-GR') : '';
const stamp = s => {
  if (!s) return '';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s.slice(0, 16).replace('T', ' ');
  const opts = {weekday:'short', day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'};
  if (d.getFullYear() !== new Date().getFullYear()) opts.year = 'numeric';
  return d.toLocaleString('el-GR', opts);
};
function suggestSlot(ch){
  const weekday = ch === 'mrbonzobeats' ? 5 : 2;
  const slot = new Date();
  slot.setHours(18, 0, 0, 0);
  slot.setDate(slot.getDate() + ((weekday - slot.getDay() + 7) % 7));
  if (slot <= new Date()) slot.setDate(slot.getDate() + 7);
  const pad = n => String(n).padStart(2, '0');
  return {date: slot.getFullYear()+'-'+pad(slot.getMonth()+1)+'-'+pad(slot.getDate()), time: '18:00'};
}
function flowLabel(w){
  const ch = (channels.find(c => c.id === w.channel) || {}).label || '';
  const kind = w.kind === 'short' ? 'Short' : (w.kind === 'story' ? 'Story' : 'Post');
  return kind + (ch ? ' · ' + ch : '');
}
function campState(){
  const card = document.querySelector('.camp');
  if (!card) return '';
  return JSON.stringify(readCamp(card));
}
function captionDirty(){
  const area = document.querySelector('[data-caption]');
  return !!(area && area.value.trim());
}
function markClean(){ campSnap = campState(); }
function confirmLeave(){
  if (tab !== 'pages' || !document.querySelector('.camp')) return true;
  if (campState() === campSnap && !captionDirty()) return true;
  return window.confirm('Υπάρχουν αλλαγές που δεν αποθηκεύτηκαν. Να τις αφήσω;');
}
function showTab(next){
  if (!next || next === tab) return;
  if (!confirmLeave()) return;
  tab = next;
  window.scrollTo(0, 0);
  $('view-videos').hidden = tab !== 'channels';
  $('view-posts').hidden = tab !== 'posts';
  $('view-history').hidden = tab !== 'history';
  $('view-pages').hidden = tab !== 'pages';
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  drawSubtabs();
  if (tab === 'pages') loadCampaigns();
}
function drawSubtabs(){
  const box = $('subtabs');
  if (tab === 'history'){ box.hidden = true; box.innerHTML = ''; return; }
  box.hidden = false;
  if (tab === 'posts'){
    const bits = [{id:'all', label:'Όλα τα κανάλια'}].concat(channels);
    box.innerHTML = bits.map(c => `<button type="button" class="sub ${c.id===qchannel?'on':''}" data-qch="${c.id}">${escapeHtml(c.label)}</button>`).join('');
    return;
  }
  if (tab === 'channels'){
    box.innerHTML = channels.map(c => `<button type="button" class="sub ${c.id===channel?'on':''}" data-ch="${c.id}">${c.label}</button>`).join('');
    return;
  }
  const items = (campaignPayload && campaignPayload.items) || [];
  box.innerHTML = items.map(c => `<button type="button" class="sub ${c.id===campaignId?'on':''}" data-cid="${c.id}">${escapeHtml(c.label)}</button>`).join('');
}
async function api(path, opt){
  const res = await fetch(path, Object.assign({headers:{'Content-Type':'application/json'}}, opt||{}));
  const data = await res.json().catch(()=>({}));
  if (!res.ok){ const e = new Error(data.error || res.statusText); e.data = data; throw e; }
  return data;
}
function matchVideo(v){
  if (vfilter === 'nopost') return v.postStatus !== 'posted';
  if (vfilter === 'noshort') return v.shortStatus !== 'shorted' && !v.nativeShort;
  if (vfilter === 'queued') return v.postStatus === 'queued' || v.shortStatus === 'queued' || v.storyStatus === 'queued';
  if (vfilter === 'error') return v.postStatus === 'error' || v.shortStatus === 'error' || v.storyStatus === 'error';
  return true;
}
let drawn = '';
function drawVideos(force){
  document.querySelectorAll('#vfilters button').forEach(b => b.classList.toggle('on', b.dataset.vf === vfilter));
  const q = $('q').value.trim().toLowerCase();
  const list = videos.filter(v => (!q || (v.title||'').toLowerCase().includes(q)) && matchVideo(v));
  const empty = videos.length && (q || vfilter !== 'all') ? 'Κανένα βίντεο με αυτό το φίλτρο.' : 'Κανένα βίντεο.';
  const html = list.map(v=>{
    const shorts = (v.publications||[]).filter(p => p.platform==='youtube' && p.url);
    const shortLine = shorts.map(p => `<div class="meta">Short <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">${escapeHtml(p.externalId)}</a></div>`).join('');
    const postState = actState(v,'post');
    const shortState = actState(v,'short');
    const storyState = actState(v,'story');
    return `<article class="card${cardMark(v)}">
    <img src="${v.thumb}" alt="">
    <div><h2>${escapeHtml(v.title)}</h2>
    <div class="meta">${when(v.timestamp)} ${dur(v.duration)}</div>
    ${shortLine}
    ${videoBar(v,'post')}${videoBar(v,'short')}${videoBar(v,'story')}
    ${(v.postError&&v.postStatus==='error')?`<div class="meta">${escapeHtml(v.postError)}</div>`:''}
    ${(v.shortError&&v.shortStatus==='error')?`<div class="meta">${escapeHtml(v.shortError)}</div>`:''}
    ${(v.storyError&&v.storyStatus==='error')?`<div class="meta">${escapeHtml(v.storyError)}</div>`:''}
    <div class="row"><button type="button" class="big${postState?' st-'+postState:''}" data-act="post" data-id="${v.id}" aria-label="${escapeHtml(actAria(v,'post'))}" ${canSend?'':'disabled'}>${escapeHtml(actLabel(v,'post'))}</button>
    <button type="button" class="big${shortState?' st-'+shortState:' g'}" data-act="short" data-id="${v.id}" aria-label="${escapeHtml(actAria(v,'short'))}" ${canSend?'':'disabled'}>${escapeHtml(actLabel(v,'short'))}</button>
    <button type="button" class="big${storyState?' st-'+storyState:' g'}" data-act="story" data-id="${v.id}" aria-label="${escapeHtml(actAria(v,'story'))}" ${canSend?'':'disabled'}>${escapeHtml(actLabel(v,'story'))}</button>
    <button type="button" class="g" data-act="delete" data-id="${v.id}">Διαγραφή</button></div>
    ${queueLine(v,'post')}${queueLine(v,'short')}${queueLine(v,'story')}
    </div></article>`;
  }).join('') || `<p class="meta">${empty}</p>`;
  if (!force && html === drawn) return;
  drawn = html;
  $('grid').innerHTML = html;
}
function escapeHtml(s){return String(s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function pbarHtml(pct, stage, eta){
  if (pct == null && !stage && !eta) return '';
  const width = Math.max(0, Math.min(100, Number(pct)||0));
  const bits = [stage, eta].filter(Boolean).map(escapeHtml).join(' · ');
  return `<div class="pbar-wrap">${bits?`<div class="pbar-meta">${bits}</div>`:''}<div class="pbar"><i style="width:${width}%"></i></div></div>`;
}
function queueLine(v, which){
  const bit = side(v, which);
  if (bit.st !== 'queued' || !bit.id) return '';
  const label = which==='post' ? 'Post' : (which==='story' ? 'Story' : 'Short');
  return `<div class="row" style="margin-top:6px"><span class="meta grow">${label} · ${escapeHtml(stamp(bit.at))}</span><button type="button" class="g" data-cancel="${bit.id}">Ακύρωση</button></div>`;
}
function videoBar(v, which){
  const bit = side(v, which);
  if (bit.st!=='running' && bit.st!=='queued') return '';
  const name = which==='post' ? 'Post' : (which==='story' ? 'Story' : 'Short');
  return pbarHtml(bit.prog, [name, bit.stage].filter(Boolean).join(' · '), bit.eta);
}
let poll = null;
async function loadVideos(refresh){
  if (!videos.length){
    drawn = '';
    $('count').textContent = 'Φέρνω τη λίστα από το YouTube…';
    $('grid').innerHTML = '<p class="meta">Φέρνω τα βίντεο του καναλιού. Η πρώτη φορά παίρνει λίγο.</p>';
  } else if (refresh) {
    $('count').textContent = videos.length + ' βίντεο · ενημερώνω…';
  }
  try{
    const data = await api('/api/videos?channel='+channel+(refresh?'&refresh=1':''));
    videos = data.videos || [];
    if (videos.length) drawVideos(true);
    const extra = [];
    if (data.loading) extra.push('ενημερώνω…');
    if (data.error) extra.push(data.error);
    $('count').textContent = (videos.length ? videos.length + ' βίντεο' : 'Φέρνω τη λίστα από το YouTube…') + (extra.length ? ' · ' + extra.join(' · ') : '');
    if (data.error && !videos.length){
      $('grid').innerHTML = '<p class="meta">'+escapeHtml(data.error)+'</p>';
    }
    if (poll) clearTimeout(poll);
    poll = data.loading ? setTimeout(() => loadVideos(false), 2000) : null;
  }catch(e){ if (!videos.length) $('grid').innerHTML = `<p class="meta">${escapeHtml(e.message)}</p>`; }
}
function queueThumb(id){
  const vid = String(id || '');
  if (!/^[\w-]{6,}$/.test(vid)) return '';
  return `<img class="qthumb" src="https://i.ytimg.com/vi/${vid}/mqdefault.jpg" alt="">`;
}
function drawQueue(){
  const queued = queue.filter(j => j.status === 'queued');
  const first = queued[0];
  $('queuesum').textContent = queued.length
    ? ('Ουρά: ' + queued.length + (first ? ' · επόμενο ' + stamp(first.runAt) : ''))
    : 'Η ουρά είναι άδεια';
  drawPostQueue();
}
function drawPostQueue(){
  const box = $('postqueue');
  if (!box) return;
  document.querySelectorAll('#qfilters button').forEach(b => b.classList.toggle('on', b.dataset.qf === qfilter));
  const items = queue.filter(j => (j.status === 'queued' || j.status === 'running') && (qfilter === 'all' || j.kind === qfilter) && (qchannel === 'all' || j.channel === qchannel))
    .slice().sort((a, b) => String(a.runAt).localeCompare(String(b.runAt)));
  const queued = items.filter(j => j.status === 'queued');
  const first = queued[0];
  const last = queued[queued.length - 1];
  const kindLabel = qfilter === 'post' ? 'posts' : (qfilter === 'short' ? 'shorts' : (qfilter === 'story' ? 'stories' : 'στην ουρά'));
  const channelLabel = qchannel === 'all' ? '' : ((channels.find(c => c.id === qchannel) || {}).label || '');
  const label = channelLabel ? kindLabel + ' · ' + channelLabel : kindLabel;
  $('postsum').textContent = queued.length
    ? (queued.length + ' ' + label + (first ? ' · επόμενο ' + stamp(first.runAt) : '') + (last && last !== first ? ' · τελευταίο ' + stamp(last.runAt) : ''))
    : 'Τίποτα σε αυτή την προβολή.';
  box.innerHTML = items.map(j => `<div class="qitem">${queueThumb(j.videoId)}<div class="grow"><strong>${escapeHtml(j.title)}</strong><div class="meta">${j.caption ? escapeHtml(j.caption) + ' · ' : ''}${escapeHtml(j.channelLabel)} · ${escapeHtml(j.kindLabel)} · ${escapeHtml(stamp(j.runAt))}</div>${j.status==='running'?pbarHtml(j.progress, j.stage, j.etaLabel):''}</div><span class="badge ${j.tone}">${escapeHtml(j.statusLabel)}</span>${j.status==='queued'?`<button class="g" type="button" data-cancel="${j.id}">Ακύρωση</button>`:''}</div>`).join('');
}
function drawHistory(){
  const bits = [{id:'all', label:'Όλα τα κανάλια'}].concat(channels);
  $('hchannels').innerHTML = bits.map(c => `<button type="button" class="chip ${c.id===hchannel?'on':''}" data-hc="${c.id}">${escapeHtml(c.label)}</button>`).join('');
  document.querySelectorAll('#hfilters button').forEach(b => b.classList.toggle('on', b.dataset.hf===hfilter));
  const items = history.filter(j => {
    if (hchannel !== 'all' && j.channel !== hchannel) return false;
    if (hfilter === 'all') return true;
    if (hfilter === 'error') return j.status === 'error';
    return j.kind === hfilter;
  });
  $('history').innerHTML = items.length ? `<table><tr><th>Πότε</th><th>Βίντεο</th><th>Κανάλι</th><th>Τύπος</th><th>Κατάσταση</th></tr>${items.map(j=>`<tr><td>${escapeHtml(stamp(j.when))}</td><td>${escapeHtml(j.title)}${j.platforms&&j.platforms.length?`<div class="meta">${escapeHtml(j.platforms.join(', '))}</div>`:''}</td><td>${escapeHtml(j.channelLabel)}</td><td>${escapeHtml(j.kindLabel)}</td><td><span class="badge ${j.tone}">${escapeHtml(j.statusLabel)}</span>${j.error?`<div class="meta">${escapeHtml(j.error)}</div>`:''}</td></tr>`).join('')}</table>` : '<p class="meta">Δεν υπάρχει ιστορικό ακόμα.</p>';
}
async function loadOverview(){
  try{
    const data = await api('/api/overview');
    if (document.activeElement !== $('gap')) $('gap').value = data.gapHours;
    canSend = !!data.api;
    $('backup').disabled = !(data.api && data.github);
    if (videos.length) drawVideos();
    const notes = [];
    if (!data.api) notes.push('<div class="note bad">Δεν μπορώ να στείλω. Λείπει το API key του n8n στο .env.</div>');
    if (data.indexError) notes.push('<div class="note bad">Δεν διάβασα τα workflows από το n8n: '+escapeHtml(data.indexError)+'</div>');
    const actions = [];
    (data.workflows||[]).forEach(w => {
      if (w.active) return;
      const label = escapeHtml(flowLabel(w));
      if (!w.present){
        const btn = w.canImport
          ? ' <button type="button" data-import="'+escapeHtml(w.name)+'">Εισαγωγή</button>'
          : '';
        actions.push(label + btn);
        return;
      }
      actions.push(label + ' <button type="button" data-on="'+escapeHtml(w.name)+'" data-id="'+escapeHtml(w.id||'')+'">Ενεργοποίηση</button>');
    });
    if (actions.length) notes.push('<div class="note bad">Workflows: '+actions.join(' · ')+'</div>');
    $('banner').innerHTML = notes.join('');
    const sync = data.sync || {};
    $('syncmsg').textContent = (sync.at ? stamp(sync.at)+' — ' : '') + (sync.message || '');
    const backup = data.backup || {};
    $('backupmsg').textContent = (backup.at ? stamp(backup.at)+' — ' : '') + (backup.message || '');
    $('githubnote').textContent = data.github ? '' : 'Το backup μένει κλειστό μέχρι να μπουν GITHUB_BACKUP_REPO και GITHUB_BACKUP_TOKEN στο .env.';
    $('ytnote').textContent = data.youtube
      ? 'YouTube διαγραφή: έτοιμο.'
      : 'YouTube διαγραφή: λείπει το token (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN).';
    queue = data.queue || [];
    history = data.history || [];
    drawQueue();
    drawHistory();
  }catch(e){}
}
function storyPreview(){
  const hook = ($('storyHook').value || '').trim() || '…';
  const cta = ($('storyCta').value || '').trim() || '…';
  $('story-preview').textContent = hook + '\n' + cta;
}
function openDlg(video, which){
  current = video; kind = which;
  const chName = (channels.find(c => c.id === channel) || {}).label || '';
  const title = which==='post' ? 'Post' : (which==='story' ? 'Story' : 'Short');
  $('dlg-title').textContent = title + (chName ? ' · ' + chName : '');
  $('dlg-video').textContent = video.title || '';
  const storyState = side(video, 'story').st;
  $('dlg-note').textContent = which !== 'story' ? (actState(video, which) === 'done' ? 'Έχει ήδη σταλεί. Το σημάδι μένει, και από εδώ το ξαναστέλνεις.' : '')
    : (storyState === 'queued'
      ? 'Είναι στην ουρά. Δεν ανεβαίνει πριν πατήσεις κουμπί. Στείλε το το ξεκινάει τώρα.'
      : (storyState === 'storied'
        ? 'Έχει ήδη σταλεί. Το σημάδι μένει. Από εδώ το ξαναστέλνεις, αφού το επιβεβαιώσεις.'
        : 'Δεν ανεβαίνει τίποτα πριν πατήσεις Στείλε το. Πάει σε Instagram και Facebook.'));
  $('post-fields').style.display = which==='post' ? '' : 'none';
  $('short-fields').style.display = which==='short' ? '' : 'none';
  $('story-fields').style.display = which==='story' ? '' : 'none';
  $('more').open = false;
  const slot = suggestSlot(channel);
  $('runDate').value = slot.date;
  $('runTime').value = slot.time;
  const link = 'https://www.youtube.com/watch?v='+video.id;
  if (which==='post') api('/api/caption?channel='+channel+'&link='+encodeURIComponent(link)).then(d=>{ $('message').value = d.message; });
  else if (which==='story'){
    const hooks = {mrbonzomusic:'MR. BONZO ♪', mrbonzobeats:'TYPE BEAT ♪'};
    const ctas = {mrbonzomusic:'Link in bio ▶', mrbonzobeats:'Link in bio ▶'};
    $('storyStart').value = video.storyStart || 'auto';
    $('storySeconds').value = video.storySeconds || 30;
    $('storyHook').value = video.storyHook || hooks[channel] || '';
    $('storyCta').value = video.storyCta || ctas[channel] || '';
    if (storyState === 'queued' && video.storyRunAt){
      const whenAt = new Date(video.storyRunAt);
      if (!isNaN(whenAt.getTime())){
        const pad = n => String(n).padStart(2, '0');
        $('runDate').value = whenAt.getFullYear()+'-'+pad(whenAt.getMonth()+1)+'-'+pad(whenAt.getDate());
        $('runTime').value = pad(whenAt.getHours())+':'+pad(whenAt.getMinutes());
      }
    }
    storyPreview();
    $('storyHook').focus();
  }else api('/api/short-preview?channel='+channel+'&title='+encodeURIComponent(video.title)+'&link='+encodeURIComponent(link)).then(d=>{
    $('shortTitle').value = d.shortTitle; $('shortDescription').value = d.shortDescription; $('hook').value = d.hook; $('cta').value = d.cta;
    $('start').value = 'auto'; $('seconds').value = 30;
  });
  $('dlg').showModal();
}
async function submit(ev){
  ev.preventDefault();
  const when = ev.submitter && ev.submitter.dataset.when || 'now';
  const body = {channel, kind, videoId: current.id, title: current.title, duration: current.duration, when, confirm:false};
  if (when === 'at'){
    if (!$('runDate').value || !$('runTime').value){ alert('Διάλεξε ημερομηνία και ώρα.'); return; }
    body.runAt = $('runDate').value + 'T' + $('runTime').value;
  }
  if (kind==='post'){
    body.message = $('message').value;
    body.platforms = [...document.querySelectorAll('input[name=platforms]:checked')].map(el=>el.value);
  }else if (kind==='story'){
    Object.assign(body, {start:$('storyStart').value, seconds:Number($('storySeconds').value), hook:$('storyHook').value, cta:$('storyCta').value});
  }else{
    Object.assign(body, {shortTitle:$('shortTitle').value, shortDescription:$('shortDescription').value, start:$('start').value, seconds:Number($('seconds').value), hook:$('hook').value, cta:$('cta').value});
  }
  try{
    await api('/api/jobs', {method:'POST', body:JSON.stringify(body)});
  }catch(e){
    if (e.data && e.data.confirm){
      if (!window.confirm(e.data.error)) return;
      body.confirm = true;
      try{ await api('/api/jobs', {method:'POST', body:JSON.stringify(body)}); }
      catch(err){ alert(err.message); return; }
    }else{ alert(e.message); return; }
  }
  $('dlg').close();
  loadVideos(false); loadOverview();
}
$('subtabs').onclick = e => {
  const qch = e.target.dataset.qch;
  if (qch){
    if (qch === qchannel) return;
    qchannel = qch;
    drawSubtabs();
    drawPostQueue();
    return;
  }
  const id = e.target.dataset.ch;
  if (id){
    if (id === channel) return;
    channel = id; videos = []; drawn = '';
    $('q').value = '';
    $('count').textContent = 'Φέρνω τη λίστα από το YouTube…';
    drawSubtabs();
    loadVideos(false);
    return;
  }
  const cid = e.target.dataset.cid;
  if (!cid || cid === campaignId) return;
  if (!confirmLeave()) return;
  campaignId = cid;
  drawCampaigns();
};
$('q').oninput = () => { if (videos.length) drawVideos(true); };
$('vfilters').onclick = e => {
  const next = e.target.dataset.vf;
  if (!next || next === vfilter) return;
  vfilter = next;
  drawVideos(true);
};
$('tabs').onclick = e => { const next = e.target.dataset.tab; if (next) showTab(next); };
$('hfilters').onclick = e => { const next = e.target.dataset.hf; if (!next) return; hfilter = next; drawHistory(); };
$('hchannels').onclick = e => { const next = e.target.dataset.hc; if (!next || next === hchannel) return; hchannel = next; drawHistory(); };
$('refresh').onclick = () => loadVideos(true);
$('archive').onclick = async () => {
  if (!confirm('Να προγραμματιστούν όλα τα παλιά τραγούδια και beats ως shorts; Music κάθε Τρίτη 18:00, Beats κάθε Δευτέρα και Τετάρτη 18:00. Το κείμενο πάνω γίνεται αρχείου. Τα post δεν πειράζονται. Όσα είναι ήδη στην ουρά δεν ξαναμπαίνουν.')) return;
  $('archive').disabled = true;
  try {
    const data = await api('/api/archive-shorts', {method:'POST', body:'{}'});
    alert(data.message || 'Έτοιμο.');
    loadVideos(false);
    loadOverview();
  } catch (e) { alert(e.message); }
  $('archive').disabled = false;
};
$('openset').onclick = () => $('settings').showModal();
$('closeset').onclick = () => $('settings').close();
$('grid').onclick = async e => {
  const btn = e.target.closest('button'); if(!btn) return;
  if (btn.dataset.cancel){
    btn.disabled = true;
    try {
      await api('/api/jobs/cancel', {method:'POST', body:JSON.stringify({id:Number(btn.dataset.cancel)})});
      loadVideos(false);
      loadOverview();
    } catch (err) {
      alert(err.message);
      btn.disabled = false;
    }
    return;
  }
  const video = videos.find(v=>v.id===btn.dataset.id); if(!video) return;
  if (btn.dataset.act === 'story'){
    if (side(video, 'story').st === 'running'){
      alert('Το story τρέχει ήδη.');
      return;
    }
    openDlg(video, 'story');
    return;
  }
  if (btn.dataset.act === 'post' || btn.dataset.act === 'short'){
    const bit = side(video, btn.dataset.act);
    if (bit.st === 'queued' || bit.st === 'running'){
      const label = btn.dataset.act === 'post' ? 'Το post' : (btn.dataset.act === 'story' ? 'Το story' : 'Το short');
      const when = bit.st === 'running' ? 'τρέχει ήδη.' : (bit.at ? 'είναι ήδη στην ουρά για ' + stamp(bit.at) : 'είναι ήδη στην ουρά.');
      alert(label + ' ' + when + ' Η ακύρωση είναι στη γραμμή από κάτω.');
      return;
    }
  }
  if (btn.dataset.act === 'delete') openDelete(video);
  else if (btn.dataset.act) openDlg(video, btn.dataset.act);
};
$('form').onsubmit = submit;
$('storyHook').oninput = storyPreview;
$('storyCta').oninput = storyPreview;
$('close').onclick = () => $('dlg').close();
function platformLine(items, label, reason){
  if (!items.length) return '';
  const url = (items.find(p => p.url) || {}).url || '';
  const link = url ? ` · <a href="${escapeHtml(url)}" target="_blank" rel="noopener">σύνδεσμος</a>` : '';
  return `<div class="meta">${label} στάλθηκε${link}. ${reason}</div>`;
}
function openDelete(video){
  currentDelete = video;
  $('del-title').textContent = video.title || video.id;
  const pubs = video.publications || [];
  const yts = pubs.filter(p => p.platform === 'youtube');
  const fbs = pubs.filter(p => p.platform === 'facebook');
  const ig = pubs.filter(p => p.platform === 'instagram');
  const tt = pubs.filter(p => p.platform === 'tiktok');
  const ytHtml = yts.map(p => `<label><input type="checkbox" data-yt="${escapeHtml(p.externalId)}" ${p.deletable ? '' : 'disabled'}> YouTube short ${escapeHtml(p.externalId)}</label>
    <div class="meta"><a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">Άνοιγμα short</a>${p.deletable ? '' : ' · Χωρίς YouTube token μένει μόνο ο σύνδεσμος.'} <button type="button" class="g" data-unlink="${escapeHtml(p.externalId)}">Ξέδεσε</button></div>`).join('');
  const fbHtml = fbs.map(p => `<label><input type="checkbox" data-fb="${escapeHtml(p.externalId)}"> Facebook ${escapeHtml(p.pageLabel || p.page || 'σελίδα')} <span class="meta">${escapeHtml(p.externalId)}</span></label>`).join('');
  const igStories = pubs.filter(p => p.platform === 'ig_story');
  const fbStories = pubs.filter(p => p.platform === 'fb_story');
  const igStoryHtml = igStories.map(p => `<label><input type="checkbox" data-ig-story="${escapeHtml(p.externalId)}"> Instagram story</label>`).join('');
  const fbStoryHtml = fbStories.map(p => `<label><input type="checkbox" data-fb-story="${escapeHtml(p.externalId)}"> Facebook story${p.pageLabel ? ' ' + escapeHtml(p.pageLabel) : ''}</label>`).join('');
  const igHtml = ig.map(p => p.deletable
    ? `<label><input type="checkbox" data-ig="${escapeHtml(p.externalId)}"> Instagram reel ${escapeHtml(p.externalId)}</label>${p.url ? `<div class="meta"><a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">Άνοιγμα</a></div>` : ''}`
    : platformLine([p], 'Instagram', 'Λείπει το id του reel.')).join('');
  const ttHtml = platformLine(tt, 'TikTok', 'Το Buffer δεν σβήνει post που έχουν ήδη δημοσιευτεί.');
  $('del-body').innerHTML = `<label><input type="checkbox" id="del-hide" checked> Κρύψε από τη λίστα</label>${ytHtml}${fbHtml}${igHtml}${igStoryHtml}${fbStoryHtml}${ttHtml}`;
  $('del').showModal();
}
async function loadPairs(){
  const data = await api('/api/pairs');
  const rows = data.ambiguous || [];
  $('pair-list').innerHTML = rows.length ? rows.map(row => `<div class="pair"><strong>${escapeHtml(row.shortTitle)}</strong>
    <div class="meta">${escapeHtml(row.shortChannelLabel)} · ${escapeHtml(row.shortId)}</div>
    ${(row.candidates||[]).map(c => `<div class="row" style="margin-top:6px"><span class="grow">${escapeHtml(c.title)} <span class="meta">${escapeHtml(c.channelLabel)}</span></span>
      <button type="button" data-confirm="${escapeHtml(row.shortId)}" data-source="${escapeHtml(c.id)}">Σύνδεση</button>
      <button type="button" class="g" data-reject="${escapeHtml(row.shortId)}" data-source="${escapeHtml(c.id)}">Απόρριψη</button></div>`).join('')}
    </div>`).join('') : '<p class="meta">Δεν υπάρχουν αμφίβολα ζεύγη.</p>';
  const hidden = data.hidden || [];
  $('pair-hidden').innerHTML = hidden.length ? hidden.map(h => `<div class="row"><span class="grow">${escapeHtml(h.title)} <span class="meta">${escapeHtml(h.channelLabel)}</span></span><button type="button" class="g" data-unhide="${escapeHtml(h.videoId)}" data-channel="${escapeHtml(h.channel)}">Εμφάνιση</button></div>`).join('') : '<p class="meta">Τίποτα κρυμμένο.</p>';
}
$('pairs-open').onclick = async () => {
  $('pair-list').innerHTML = '<p class="meta">Φέρνω τα ζεύγη…</p>';
  $('pair-hidden').innerHTML = '';
  $('pairs').showModal();
  try { await loadPairs(); } catch (e) { $('pair-list').innerHTML = '<p class="meta">'+escapeHtml(e.message)+'</p>'; }
};
$('pair-close').onclick = () => $('pairs').close();
$('pair-list').onclick = async e => {
  const confirmBtn = e.target.closest('[data-confirm]');
  const rejectBtn = e.target.closest('[data-reject]');
  const btn = confirmBtn || rejectBtn;
  if (!btn) return;
  btn.disabled = true;
  try {
    await api('/api/pairs', {method:'POST', body: JSON.stringify({
      action: confirmBtn ? 'confirm' : 'reject',
      shortId: btn.dataset.confirm || btn.dataset.reject,
      sourceId: btn.dataset.source
    })});
    await loadPairs();
    loadVideos(false);
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
  }
};
$('pair-hidden').onclick = async e => {
  const btn = e.target.closest('[data-unhide]');
  if (!btn) return;
  btn.disabled = true;
  try {
    await api('/api/pairs', {method:'POST', body: JSON.stringify({action:'unhide', videoId: btn.dataset.unhide, channel: btn.dataset.channel})});
    await loadPairs();
    loadVideos(false);
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
  }
};
$('pair-manual').onclick = async () => {
  const btn = $('pair-manual');
  btn.disabled = true;
  try {
    await api('/api/pairs', {method:'POST', body: JSON.stringify({action:'manual', sourceId: $('pair-source').value, url: $('pair-url').value})});
    $('pair-source').value = '';
    $('pair-url').value = '';
    await loadPairs();
    loadVideos(false);
  } catch (err) {
    alert(err.message);
  }
  btn.disabled = false;
};
$('del-close').onclick = () => $('del').close();
$('del-body').onclick = async e => {
  const btn = e.target.closest('[data-unlink]');
  if (!btn || !currentDelete) return;
  if (!window.confirm('Να ξεδεθεί το short από αυτό το βίντεο;')) return;
  btn.disabled = true;
  try {
    await api('/api/pairs', {method:'POST', body: JSON.stringify({action:'unlink', sourceId: currentDelete.id, shortId: btn.dataset.unlink})});
    $('del').close();
    loadVideos(false);
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
  }
};
$('del-go').onclick = async () => {
  if (!currentDelete) return;
  const youtube = [...document.querySelectorAll('#del-body [data-yt]:checked')].map(el => el.dataset.yt);
  const facebook = [...document.querySelectorAll('#del-body [data-fb]:checked')].map(el => el.dataset.fb);
  const instagram = [...document.querySelectorAll('#del-body [data-ig]:checked')].map(el => el.dataset.ig);
  const igStories = [...document.querySelectorAll('#del-body [data-ig-story]:checked')].map(el => el.dataset.igStory);
  const fbStories = [...document.querySelectorAll('#del-body [data-fb-story]:checked')].map(el => el.dataset.fbStory);
  const hide = $('del-hide') && $('del-hide').checked;
  if (!hide && !youtube.length && !facebook.length && !instagram.length && !igStories.length && !fbStories.length){
    alert('Δεν επιλέχθηκε ενέργεια.');
    return;
  }
  if ((youtube.length || facebook.length || instagram.length || igStories.length || fbStories.length) && !window.confirm('Να σταλεί η διαγραφή; Δεν αναιρείται.')) return;
  const btn = $('del-go');
  btn.disabled = true;
  try {
    await api('/api/delete', {method:'POST', body: JSON.stringify({
      videoId: currentDelete.id,
      channel,
      title: currentDelete.title || '',
      hide,
      youtube,
      facebook,
      instagram,
      igStories,
      fbStories
    })});
    $('del').close();
    loadVideos(false);
  } catch (err) {
    alert(err.message);
  }
  btn.disabled = false;
};
$('savegap').onclick = async () => { await api('/api/settings', {method:'POST', body:JSON.stringify({gapHours:Number($('gap').value)})}); loadOverview(); };
$('dosync').onclick = async () => { $('dosync').disabled=true; try{ await api('/api/sync', {method:'POST', body:'{}'}); }catch(e){ alert(e.message);} $('dosync').disabled=false; loadOverview(); };
$('backup').onclick = async () => { $('backup').disabled=true; try{ const r = await api('/api/backup', {method:'POST', body:'{}'}); alert(r.message);}catch(e){ alert(e.message);} $('backup').disabled=false; loadOverview(); };
$('banner').onclick = async e => {
  const imp = e.target.dataset.import;
  if (imp){
    try{ await api('/api/import', {method:'POST', body:JSON.stringify({name:imp})}); }catch(err){ alert(err.message); }
    loadOverview();
    return;
  }
  const name = e.target.dataset.on; if(!name) return;
  try{ await api('/api/activate', {method:'POST', body:JSON.stringify({name, id:e.target.dataset.id||''})}); }catch(err){ alert(err.message); }
  loadOverview();
};
const RULES = {always:'Κάθε εβδομάδα', twice_month:'Δύο φορές τον μήνα', day_1_7:'1η εβδομάδα του μήνα', day_15_21:'Ημέρες 15–21'};
let campaignDays = [];
function readCamp(card){
  const shared = (card.querySelector('[data-shared]') || {}).value || '';
  const pages = [...card.querySelectorAll('[data-rule]')].map(sel => ({
    id: sel.dataset.rule,
    rule: sel.value || 'always',
    texts: shared
  }));
  return {
    id: card.dataset.cid,
    weekday: Number(card.querySelector('[data-weekday]').value),
    hour: Number(card.querySelector('[data-hour]').value),
    minute: Number(card.querySelector('[data-minute]').value),
    link: card.querySelector('[data-link]').value,
    image: card.querySelector('[data-image]').value,
    texts: shared,
    pages
  };
}
function pad2(n){ return String(Number(n)||0).padStart(2,'0'); }
function dayName(id){
  const hit = campaignDays.find(d => Number(d.id) === Number(id));
  return hit ? hit.label : '';
}
function schedSentence(weekday, hour, minute){
  return 'Κάθε ' + dayName(weekday) + ' στις ' + pad2(hour) + ':' + pad2(minute);
}
function firstLine(text){
  const line = String(text || '').split('\n').map(s => s.trim()).find(Boolean);
  return line || 'Χωρίς κείμενο';
}
function refreshSched(card){
  const btn = card.querySelector('[data-sched]');
  if (!btn) return;
  btn.textContent = schedSentence(
    card.querySelector('[data-weekday]').value,
    card.querySelector('[data-hour]').value,
    card.querySelector('[data-minute]').value
  );
}
function refreshPreviews(card){
  const image = (card.querySelector('[data-image]') || {}).value || '';
  const link = (card.querySelector('[data-link]') || {}).value || '';
  const imgprev = card.querySelector('[data-imgprev]');
  if (imgprev){
    imgprev.hidden = !image;
    if (image) imgprev.src = image;
  }
  const shared = card.querySelector('[data-shared]');
  const box = card.querySelector('[data-preview="shared"]');
  if (shared && box){
    const shot = box.querySelector('[data-shot]');
    shot.hidden = !image;
    if (image) shot.src = image;
    box.querySelector('[data-sample]').textContent = firstLine(shared.value);
    box.querySelector('[data-plink]').textContent = link;
  }
}
function bindCampImages(card){
  card.querySelectorAll('img').forEach(img => { img.onerror = () => { img.hidden = true; }; });
}
function applySaved(body){
  const item = ((campaignPayload && campaignPayload.items) || []).find(c => c.id === body.id);
  if (!item) return;
  item.weekday = body.weekday;
  item.hour = body.hour;
  item.minute = body.minute;
  item.link = body.link;
  item.image = body.image;
  const lines = String(body.texts || '').split('\n').map(s => s.trim()).filter(Boolean);
  item.texts = lines;
  (body.pages || []).forEach(p => {
    const page = (item.pages || []).find(x => x.id === p.id);
    if (!page) return;
    page.rule = p.rule;
    page.texts = lines;
  });
}
function onCampEdit(e){
  const card = e.target.closest('.camp');
  if (!card) return;
  if (e.target.matches('[data-weekday],[data-hour],[data-minute]')) refreshSched(card);
  refreshPreviews(card);
}
function drawCampaigns(payload){
  if (payload) campaignPayload = payload;
  const data = campaignPayload || {days:[], items:[]};
  campaignDays = data.days || [];
  const items = data.items || [];
  drawSubtabs();
  if (!items.length){
    $('campaigns').innerHTML = '<p class="meta">Δεν βρέθηκαν καμπάνιες.</p>';
    campSnap = '';
    return;
  }
  if (!items.some(c => c.id === campaignId)) campaignId = items[0].id;
  const c = items.find(item => item.id === campaignId);
  const hours = Array.from({length:24}, (_,i)=>i);
  const dayOpts = campaignDays.map(d => `<option value="${d.id}" ${Number(d.id)===Number(c.weekday)?'selected':''}>${escapeHtml(d.label)}</option>`).join('');
  const hourOpts = hours.map(h => `<option value="${h}" ${Number(h)===Number(c.hour)?'selected':''}>${pad2(h)}</option>`).join('');
  const last = c.last && c.last.at ? ('Τελευταία: ' + stamp(c.last.at) + (c.last.status ? ' · ' + c.last.status : '')) : 'Δεν έχει τρέξει ακόμα';
  const sharedText = (c.texts && c.texts.length ? c.texts : ((c.pages && c.pages[0] && c.pages[0].texts) || [])).join('\n');
  const pages = (c.pages||[]).map(p => `<div class="page-head" style="margin-top:10px"><span><input type="checkbox" data-run="${p.id}" checked> ${escapeHtml(p.label)}</span><select data-rule="${p.id}">${Object.entries(RULES).map(([k,v])=>`<option value="${k}" ${k===p.rule?'selected':''}>${escapeHtml(v)}</option>`).join('')}</select></div>`).join('');
  $('campaigns').innerHTML = `<section class="card camp" data-cid="${c.id}"><h3>${escapeHtml(c.label)}</h3>
      <p class="meta">${c.present?'Ενεργό στο n8n':'Λείπει από το n8n'} · ${escapeHtml(last)}</p>
      <div class="sched"><button type="button" class="sched-line" data-sched>${escapeHtml(schedSentence(c.weekday, c.hour, c.minute))}</button>
      <div class="row sched-edit" hidden><label>Μέρα <select data-weekday>${dayOpts}</select></label>
      <label>Ώρα <select data-hour>${hourOpts}</select></label>
      <label>Λεπτά <input data-minute type="number" min="0" max="59" value="${Number(c.minute)||0}" style="width:72px"></label></div></div>
      <label>Σύνδεσμος</label><input data-link value="${escapeHtml(c.link||'')}">
      <label>Εικόνα</label><input data-image value="${escapeHtml(c.image||'')}">
      <div><img class="imgprev" data-imgprev alt="" hidden></div>
      <label>Κείμενο</label><textarea data-shared rows="8">${escapeHtml(sharedText)}</textarea>
      <div class="preview" data-preview="shared" style="margin-top:8px"><p data-sample></p><img data-shot alt="" hidden><div class="meta" data-plink></div></div>
      <div class="camp-grid">${pages}</div>
      <label>Κείμενο για τώρα (κενό = από τη λίστα)</label>
      <textarea data-caption rows="2" placeholder="Προαιρετικό, μόνο για Δημοσίευση τώρα"></textarea>
      <div class="row" style="margin-top:10px">
        <button type="button" data-save="${c.id}">Αποθήκευση</button>
        <button class="g" type="button" data-runall="${c.id}">Δημοσίευση τώρα</button>
      </div></section>`;
  const card = document.querySelector('.camp');
  bindCampImages(card);
  refreshPreviews(card);
  markClean();
}
async function loadCampaigns(){
  try{ drawCampaigns(await api('/api/campaigns')); }
  catch(e){
    $('campaigns').innerHTML = '<p class="note bad">'+escapeHtml(e.message)+'</p>';
    campSnap = '';
  }
}
$('campaigns').addEventListener('input', onCampEdit);
$('campaigns').addEventListener('change', onCampEdit);
$('campaigns').onclick = async e => {
  if (e.target.closest('[data-sched]')){
    const edit = e.target.closest('.sched').querySelector('.sched-edit');
    edit.hidden = !edit.hidden;
    return;
  }
  const saveBtn = e.target.closest('[data-save]');
  const runBtn = e.target.closest('[data-runall]');
  if (!saveBtn && !runBtn) return;
  const card = e.target.closest('.camp');
  if (!card) return;
  const body = readCamp(card);
  const btn = saveBtn || runBtn;
  btn.disabled = true;
  try{
    if (saveBtn){
      await api('/api/campaigns', {method:'POST', body:JSON.stringify(body)});
      applySaved(body);
      markClean();
      btn.textContent = 'Αποθηκεύτηκε';
      setTimeout(() => { if (btn.isConnected) btn.textContent = 'Αποθήκευση'; }, 1600);
    } else {
      body.pages = [...card.querySelectorAll('[data-run]:checked')].map(el => el.dataset.run);
      body.caption = (card.querySelector('[data-caption]') || {}).value || '';
      if (!body.pages.length) throw new Error('Διάλεξε τουλάχιστον μία σελίδα.');
      const r = await api('/api/campaigns/run', {method:'POST', body:JSON.stringify(body)});
      alert(r.message || 'Στάλθηκε.');
    }
  }catch(err){ alert(err.message); }
  btn.disabled = false;
};
async function cancelQueued(id, btn){
  if (btn) btn.disabled = true;
  try {
    await api('/api/jobs/cancel', {method:'POST', body:JSON.stringify({id:Number(id)})});
    loadVideos(false);
    loadOverview();
  } catch (err) {
    alert(err.message);
    if (btn) btn.disabled = false;
  }
}
$('queuesum').onclick = () => showTab('posts');
$('qfilters').onclick = e => {
  const next = e.target.dataset.qf;
  if (!next || next === qfilter) return;
  qfilter = next;
  drawPostQueue();
};
$('postqueue').onclick = e => {
  const btn = e.target.closest('[data-cancel]'); if(!btn) return;
  cancelQueued(btn.dataset.cancel, btn);
};
showTab('channels'); loadVideos(false); loadOverview();
setInterval(()=>{ if(!$('dlg').open && !$('settings').open && !$('del').open && !$('pairs').open) { loadOverview(); if (tab==='channels') loadVideos(false); } }, 4000);
</script></body></html>"""


PAGE = uploader_ui.inject(PAGE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def _cookie(self):
        try:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        morsel = jar.get("n8nsess")
        return morsel.value if morsel else ""

    def _cookie_str(self, value, age):
        extra = "; Secure; SameSite=None" if (self.headers.get("X-Forwarded-Proto", "").lower() == "https") else "; SameSite=Lax"
        return "n8nsess=%s; Path=/; Max-Age=%d; HttpOnly%s" % (value, age, extra)

    def _send(self, code, payload, content_type="application/json", cookie=None):
        if isinstance(payload, (dict, list)):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif isinstance(payload, str):
            raw = payload.encode("utf-8")
        else:
            raw = payload
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(raw)

    def _redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type") or ""
        if "application/json" in ctype:
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return {}
        return urllib.parse.parse_qs(raw.decode("utf-8", "replace"))

    def _basic_ok(self):
        if not PASSWORD:
            return False
        got = self.headers.get("Authorization", "")
        token = base64.b64encode(("admin:" + PASSWORD).encode()).decode()
        try:
            return hmac.compare_digest(got.encode("utf-8", "replace"), ("Basic " + token).encode())
        except Exception:
            return False

    def _auth(self):
        return sess_ok(self._cookie()) or self._basic_ok()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._send(200, {"status": "ok"})
            return
        if path.rstrip("/") == "/api/widget":
            self._send(200, widget_summary())
            return
        if path in ("/", "/login") and not self._auth():
            page = LOGIN.replace("%ERR%", "")
            self._send(200, page, "text/html; charset=utf-8")
            return
        if not self._auth():
            if path.startswith("/api/"):
                self._send(401, {"error": "Σύνδεση"})
            else:
                self._redirect("/login")
            return
        if path == "/logout":
            self._redirect("/login", self._cookie_str("", 0))
            return
        if path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
            return
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path.startswith("/api/uploader"):
                res = uploader.handle_get(path, query)
                if res is None:
                    self._send(404, {"error": "not found"})
                else:
                    self._send(200, res)
                return
            if path == "/api/overview":
                self._send(200, overview())
            elif path == "/api/widget":
                self._send(200, widget_summary())
            elif path == "/api/campaigns":
                self._send(200, campaigns_overview())
            elif path == "/api/videos":
                channel = (query.get("channel") or ["mrbonzomusic"])[0]
                if channel not in CHANNELS:
                    raise ValueError("Άγνωστο κανάλι.")
                videos, fetched, error, loading = load_catalog(channel, refresh=query.get("refresh") == ["1"])
                match_if_stale()
                visible, by_source = present_videos(channel, videos)
                state = video_rows([item["id"] for item in visible])
                self._send(200, {
                    "videos": [public_video(item, state.get(item["id"]), by_source.get(item["id"])) for item in visible],
                    "fetchedAt": fetched,
                    "error": error,
                    "loading": loading,
                    "youtube": youtube_ready(),
                })
            elif path == "/api/pairs":
                self._send(200, pairs_payload())
            elif path == "/api/caption":
                channel = (query.get("channel") or [""])[0]
                link = (query.get("link") or [""])[0]
                title = (query.get("title") or [""])[0]
                fb = post_caption(channel, link, title)
                self._send(200, {
                    "message": fb,
                    "messageFb": fb,
                    "messageSocial": post_caption_social(channel, title),
                })
            elif path == "/api/short-preview":
                channel = (query.get("channel") or [""])[0]
                title = (query.get("title") or [""])[0]
                link = (query.get("link") or [""])[0]
                video_id = (query.get("videoId") or [""])[0]
                info = CHANNELS.get(channel) or CHANNELS["mrbonzomusic"]
                self._send(200, {
                    "shortTitle": short_title(channel, title),
                    "shortDescription": short_description(channel, link, title, video_id),
                    "hook": info["hook"],
                    "cta": info["cta"],
                })
            else:
                self._send(404, {"error": "not found"})
        except Exception as err:
            self._send(400, {"error": str(err)})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._body()
        if path == "/login":
            password = ""
            if isinstance(body, dict) and "password" in body:
                password = body.get("password", [""])[0]
            if PASSWORD and hmac.compare_digest(password, PASSWORD):
                self._redirect("/", self._cookie_str(sess_new(), SESS_TTL))
            else:
                page = LOGIN.replace("%ERR%", '<p class="e">Λάθος κωδικός</p>')
                self._send(401, page, "text/html; charset=utf-8")
            return
        if not self._auth():
            self._send(401, {"error": "Σύνδεση"})
            return
        try:
            if path.startswith("/api/uploader"):
                res = uploader.handle_post(path, body)
                if res is None:
                    self._send(404, {"error": "not found"})
                else:
                    self._send(200, res)
                return
            if path == "/api/jobs":
                self._send(200, enqueue(body))
            elif path == "/api/archive-shorts":
                self._send(200, schedule_archive())
            elif path == "/api/jobs/cancel":
                cancel_job(int(body.get("id") or 0))
                self._send(200, {"ok": True})
            elif path == "/api/settings":
                hours = int(body.get("gapHours") or 8)
                if not 1 <= hours <= 168:
                    raise ValueError("Το κενό είναι από 1 έως 168 ώρες.")
                set_setting("gap_hours", str(hours))
                self._send(200, {"gapHours": hours})
            elif path == "/api/sync":
                sync_live()
                self._send(200, SYNC)
            elif path == "/api/activate":
                name = body.get("name") or ""
                if name not in SPECS:
                    raise ValueError("Άγνωστο workflow.")
                activate_workflow(name, body.get("id") or "")
                self._send(200, {"ok": True})
            elif path == "/api/import":
                name = body.get("name") or ""
                if name not in SPECS:
                    raise ValueError("Άγνωστο workflow.")
                cred = ensure_credential() if WEBHOOK_SECRET else None
                created = import_workflow(name, cred)
                self._send(200, {"ok": True, "id": created.get("id")})
            elif path == "/api/backup":
                self._send(200, run_backup())
            elif path == "/api/campaigns":
                cid = body.get("id")
                cfg = save_campaign(cid, body)
                cred = ensure_credential() if WEBHOOK_SECRET else None
                apply_campaign_to_n8n(cfg, cred)
                self._send(200, {"ok": True, "item": cfg})
            elif path == "/api/campaigns/run":
                self._send(200, fire_campaign(body.get("id"), body))
            elif path == "/api/pairs":
                self._send(200, apply_pairs(body))
            elif path == "/api/delete":
                self._send(200, apply_remote_delete(body))
            else:
                self._send(404, {"error": "not found"})
        except Confirm as err:
            self._send(409, {"error": str(err), "confirm": True})
        except Exception as err:
            self._send(400, {"error": str(err)})


def main():
    if not PASSWORD:
        raise SystemExit("PANEL_PASSWORD is empty")
    init_db()
    uploader.init()
    threading.Thread(target=uploader.worker_loop, daemon=True).start()
    try:
        schedule_archive_stories()
    except Exception:
        traceback.print_exc()
    threading.Thread(target=worker_loop, daemon=True).start()
    threading.Thread(target=backup_on_start, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    threading.Thread(target=backfill_loop, daemon=True).start()
    if API_KEY:
        threading.Thread(target=sync_live, daemon=True).start()
    else:
        SYNC.update(message="Λείπει το N8N_API_KEY. Η λίστα βίντεο δουλεύει. Τα post, τα short και το backup μένουν κλειστά μέχρι να το βάλεις στο .env (Settings → n8n API, δικαιώματα workflows και credentials).")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
