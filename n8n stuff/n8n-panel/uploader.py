#!/usr/bin/env python3
"""YouTube uploader tab for the n8n panel.

Flow:  inbox folder -> scan -> suggest title/description/tags/playlist (Ollama or Anthropic,
fallback templates) -> you review/edit -> Approve -> background worker uploads to YouTube as
private + publishAt (YouTube publishes by itself at the chosen slot) -> optional playlist add.

Everything is per channel (mrbonzomusic / mrbonzobeats). The module is self contained: app.py only
calls init(), routes API calls to handle_get()/handle_post() and starts worker_loop().
"""
import json
import mimetypes
import os
import re
import sqlite3
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

INBOX = os.environ.get("YT_INBOX_DIR", "/inbox")
DATA = os.environ.get("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA, "uploader.sqlite")
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a"}
DBLOCK = threading.Lock()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
# One refresh token per channel (a token belongs to the channel you picked when authorising).
# Falls back to the old single YOUTUBE_REFRESH_TOKEN so nothing breaks until you add the second.
TOKENS = {
    "mrbonzomusic": os.environ.get("YOUTUBE_REFRESH_TOKEN_MUSIC", "").strip(),
    "mrbonzobeats": os.environ.get("YOUTUBE_REFRESH_TOKEN_BEATS", "").strip(),
}
FALLBACK_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

# Defaults per channel. Editable from the tab (settings are stored in the DB).
DEFAULTS = {
    "mrbonzomusic": {
        "label": "Music",
        "weekdays": [1, 3, 5],          # Mon=0
        "hour": 18,
        "category": "10",               # Music
        "made_for_kids": False,
        "desc_footer": "",
        "default_tags": "",
        "style_hint": "Original songs by Mr. Bonzo.",
    },
    "mrbonzobeats": {
        "label": "Beats",
        "weekdays": [0, 2, 4],
        "hour": 18,
        "category": "10",
        "made_for_kids": False,
        "desc_footer": "",
        "default_tags": "type beat, instrumental, beat",
        "style_hint": "Type beats / instrumentals by Mr. Bonzo.",
    },
}
CHANNEL_IDS = tuple(DEFAULTS.keys())


# ---------------------------------------------------------------- db
def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def db():
    os.makedirs(DATA, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init():
    with DBLOCK:
        con = db()
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS up_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER,
                mtime REAL,
                title TEXT,
                description TEXT,
                tags TEXT,
                playlist TEXT,
                publish_at TEXT,
                status TEXT NOT NULL,       -- new, ready, approved, uploading, done, error, skipped
                error TEXT,
                video_id TEXT,
                progress REAL,
                suggestions TEXT,           -- json: alternative titles
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(channel, path)
            );
            CREATE TABLE IF NOT EXISTS up_settings (
                channel TEXT PRIMARY KEY,
                payload TEXT
            );
            CREATE TABLE IF NOT EXISTS up_titles (
                channel TEXT NOT NULL,
                title TEXT NOT NULL,
                PRIMARY KEY (channel, title)
            );
            """
        )
        con.commit()
        con.close()
    for channel in CHANNEL_IDS:
        os.makedirs(os.path.join(INBOX, channel), exist_ok=True)


def channel_settings(channel):
    base = dict(DEFAULTS[channel])
    with DBLOCK:
        con = db()
        row = con.execute("SELECT payload FROM up_settings WHERE channel=?", (channel,)).fetchone()
        con.close()
    if row:
        try:
            base.update(json.loads(row["payload"]))
        except Exception:
            pass
    return base


def save_settings(channel, body):
    cur = channel_settings(channel)
    for key in ("weekdays",):
        if key in body:
            cur[key] = sorted({int(d) for d in body[key] if 0 <= int(d) <= 6})
    for key in ("hour",):
        if key in body:
            cur[key] = max(0, min(23, int(body[key])))
    for key in ("category", "desc_footer", "default_tags", "style_hint"):
        if key in body:
            cur[key] = str(body[key])
    if "made_for_kids" in body:
        cur["made_for_kids"] = bool(body["made_for_kids"])
    with DBLOCK:
        con = db()
        con.execute(
            "INSERT INTO up_settings (channel, payload) VALUES (?, ?) "
            "ON CONFLICT(channel) DO UPDATE SET payload=excluded.payload",
            (channel, json.dumps(cur)),
        )
        con.commit()
        con.close()
    return cur


# ---------------------------------------------------------------- youtube auth / api
def token_for(channel):
    return TOKENS.get(channel) or FALLBACK_TOKEN


def ready(channel):
    return bool(CLIENT_ID and CLIENT_SECRET and token_for(channel))


_ACCESS = {}


def access_token(channel):
    cached = _ACCESS.get(channel)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    form = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": token_for(channel),
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise RuntimeError("YouTube token %s: %s" % (err.code, err.read().decode("utf-8", "replace")[:300]))
    token = data.get("access_token") or ""
    if not token:
        raise RuntimeError("Το YouTube δεν έδωσε access token.")
    _ACCESS[channel] = (token, time.time() + int(data.get("expires_in") or 3000))
    return token


def yt_api(channel, method, path, params=None, body=None, timeout=40):
    url = "https://www.googleapis.com/youtube/v3/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + access_token(channel))
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        raise RuntimeError("YouTube %s: %s" % (err.code, err.read().decode("utf-8", "replace")[:400]))


def my_channel(channel):
    data = yt_api(channel, "GET", "channels", {"part": "id,snippet,contentDetails", "mine": "true"})
    items = data.get("items") or []
    if not items:
        raise RuntimeError("Το token δεν έχει κανάλι.")
    return items[0]


def list_playlists(channel):
    out, page = [], ""
    while True:
        params = {"part": "id,snippet", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = yt_api(channel, "GET", "playlists", params)
        for item in data.get("items") or []:
            out.append({"id": item["id"], "title": item["snippet"]["title"]})
        page = data.get("nextPageToken") or ""
        if not page:
            return out


def ensure_playlist(channel, title):
    """Return playlist id for title, creating it (public) when it does not exist yet."""
    wanted = title.strip().lower()
    for pl in list_playlists(channel):
        if pl["title"].strip().lower() == wanted:
            return pl["id"]
    data = yt_api(channel, "POST", "playlists", {"part": "snippet,status"}, {
        "snippet": {"title": title.strip()},
        "status": {"privacyStatus": "public"},
    })
    return data["id"]


def add_to_playlist(channel, playlist_id, video_id):
    yt_api(channel, "POST", "playlistItems", {"part": "snippet"}, {
        "snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}},
    })


def channel_catalog(channel):
    """Titles + descriptions of the videos already on the channel (public + scheduled/private)."""
    info = my_channel(channel)
    uploads = info["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], ""
    while len(ids) < 300:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = yt_api(channel, "GET", "playlistItems", params)
        ids += [i["contentDetails"]["videoId"] for i in data.get("items") or []]
        page = data.get("nextPageToken") or ""
        if not page:
            break
    videos = []
    for i in range(0, len(ids), 50):
        data = yt_api(channel, "GET", "videos", {"part": "snippet,status", "id": ",".join(ids[i:i + 50])})
        for v in data.get("items") or []:
            videos.append({
                "id": v["id"],
                "title": v["snippet"].get("title", ""),
                "description": v["snippet"].get("description", ""),
                "tags": v["snippet"].get("tags") or [],
                "publishAt": (v.get("status") or {}).get("publishAt") or "",
                "privacy": (v.get("status") or {}).get("privacyStatus") or "",
            })
    return videos


_CATALOG = {}


def cached_catalog(channel, force=False):
    hit = _CATALOG.get(channel)
    if hit and not force and hit[0] > time.time() - 600:
        return hit[1]
    videos = channel_catalog(channel)
    _CATALOG[channel] = (time.time(), videos)
    return videos


# ---------------------------------------------------------------- inbox scan
def scan(channel):
    folder = os.path.join(INBOX, channel)
    os.makedirs(folder, exist_ok=True)
    now = time.time()
    found = []
    for root, _dirs, files in os.walk(folder):
        if os.path.basename(root) in ("_done", "_skipped"):
            continue
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in VIDEO_EXT | AUDIO_EXT:
                continue
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            if now - st.st_mtime < 20:      # still being copied
                continue
            found.append((full, st.st_size, st.st_mtime))
    with DBLOCK:
        con = db()
        known = {r["path"] for r in con.execute("SELECT path FROM up_items WHERE channel=?", (channel,))}
        for full, size, mtime in found:
            if full in known:
                continue
            con.execute(
                "INSERT INTO up_items (channel, path, size, mtime, status, created_at, updated_at) "
                "VALUES (?,?,?,?, 'new', ?, ?)",
                (channel, full, size, mtime, iso(utcnow()), iso(utcnow())),
            )
        # forget rows whose file disappeared (not yet uploaded)
        for row in con.execute("SELECT id, path, status FROM up_items WHERE channel=?", (channel,)).fetchall():
            if row["status"] in ("new", "ready", "error") and not os.path.exists(row["path"]):
                con.execute("DELETE FROM up_items WHERE id=?", (row["id"],))
        con.commit()
        con.close()


# ---------------------------------------------------------------- titles: style + uniqueness
def norm(text):
    return re.sub(r"[^a-z0-9α-ωά-ώ ]+", "", (text or "").lower()).strip()


def tokens(text):
    return {t for t in norm(text).split() if len(t) > 1}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def used_titles(channel):
    titles = set()
    try:
        titles |= {v["title"] for v in cached_catalog(channel)}
    except Exception:
        pass
    with DBLOCK:
        con = db()
        titles |= {r["title"] for r in con.execute(
            "SELECT title FROM up_items WHERE channel=? AND title IS NOT NULL AND title != ''", (channel,))}
        titles |= {r["title"] for r in con.execute("SELECT title FROM up_titles WHERE channel=?", (channel,))}
        con.close()
    return {t for t in titles if t}


def is_unique(title, taken, threshold=0.8):
    return all(norm(title) != norm(t) and similarity(title, t) < threshold for t in taken)


# ---------------------------------------------------------------- scheduling
def slot_candidates(settings, start):
    """Yield local slot datetimes (tz aware) following the weekday/hour pattern, from start on."""
    day = start.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(0, 400):
        d = day + timedelta(days=offset)
        if d.weekday() not in settings["weekdays"]:
            continue
        slot = d.replace(hour=int(settings["hour"]))
        if slot > start.astimezone(TZ) + timedelta(hours=2):
            yield slot


def taken_slots(channel):
    taken = set()
    with DBLOCK:
        con = db()
        for r in con.execute(
                "SELECT publish_at FROM up_items WHERE channel=? AND publish_at IS NOT NULL "
                "AND status IN ('ready','approved','uploading','done')", (channel,)):
            taken.add(r["publish_at"][:13])     # same hour == same slot
        con.close()
    try:
        for v in cached_catalog(channel):
            if v["publishAt"]:
                taken.add(v["publishAt"][:13])
    except Exception:
        pass
    return taken


def next_free_slots(channel, count=1, after=None, skip=()):
    settings = channel_settings(channel)
    taken = taken_slots(channel) | set(skip)
    out = []
    for slot in slot_candidates(settings, after or utcnow()):
        key = iso(slot)[:13]
        if key in taken:
            continue
        out.append(iso(slot))
        taken.add(key)
        if len(out) >= count:
            break
    return out


# ---------------------------------------------------------------- metadata suggestions
def llm_json(prompt):
    """Ask Anthropic (if key) or local Ollama for a JSON object. Returns dict or None."""
    text = ""
    try:
        if ANTHROPIC_KEY:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": ANTHROPIC_MODEL, "max_tokens": 1200,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode(),
                method="POST",
            )
            req.add_header("x-api-key", ANTHROPIC_KEY)
            req.add_header("anthropic-version", "2023-06-01")
            req.add_header("content-type", "application/json")
            with urllib.request.urlopen(req, timeout=90) as res:
                data = json.loads(res.read().decode("utf-8"))
            text = "".join(b.get("text", "") for b in data.get("content") or [])
        else:
            req = urllib.request.Request(
                OLLAMA_URL + "/api/generate",
                data=json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json",
                                 "options": {"temperature": 0.9, "num_ctx": 4096}}).encode(),
                method="POST",
            )
            req.add_header("content-type", "application/json")
            with urllib.request.urlopen(req, timeout=240) as res:
                text = json.loads(res.read().decode("utf-8")).get("response", "")
    except Exception:
        traceback.print_exc()
        return None
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def clean_filename(path):
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[_\-]+", " ", base)
    base = re.sub(r"\b(final|master|mix|v\d+|bounce|export)\b", "", base, flags=re.I)
    return re.sub(r"\s+", " ", base).strip().title()


def style_examples(channel, limit=12):
    try:
        videos = cached_catalog(channel)
    except Exception:
        return []
    public = [v for v in videos if v["privacy"] in ("public", "")] or videos
    return public[:limit]


def fallback_title(channel, path, taken):
    stem = clean_filename(path) or "Untitled"
    suffix = "Type Beat" if channel == "mrbonzobeats" else "(Official Audio)"
    for candidate in ("%s %s" % (stem, suffix), "%s - Mr. Bonzo %s" % (stem, suffix)):
        if is_unique(candidate, taken):
            return candidate
    return "%s %s #%d" % (stem, suffix, len(taken) + 1)


def suggest(item_id, avoid=()):
    with DBLOCK:
        con = db()
        row = con.execute("SELECT * FROM up_items WHERE id=?", (item_id,)).fetchone()
        con.close()
    if not row:
        raise ValueError("Δεν βρέθηκε.")
    channel, path = row["channel"], row["path"]
    settings = channel_settings(channel)
    taken = used_titles(channel) | set(avoid)
    examples = style_examples(channel)
    playlists = []
    if ready(channel):
        try:
            playlists = [p["title"] for p in list_playlists(channel)]
        except Exception:
            playlists = []
    ex_block = "\n".join(
        "- TITLE: %s\n  DESCRIPTION: %s\n  TAGS: %s" % (
            v["title"], (v["description"] or "")[:300].replace("\n", " | "), ", ".join(v["tags"][:15]))
        for v in examples) or "(no previous videos available)"
    prompt = (
        "You write YouTube metadata for the channel '%s'. %s\n"
        "A new file was dropped in the inbox: filename = %r.\n\n"
        "Existing videos of this channel (match their style, wording, structure and tag habits):\n%s\n\n"
        "Titles that are already taken and MUST NOT be repeated or nearly copied (%d total, showing recent):\n%s\n\n"
        "Existing playlists: %s\n\n"
        "Return ONLY a JSON object with keys: "
        "\"titles\" (5 distinct title options, each similar in style to the existing ones but clearly unique), "
        "\"description\" (in the same structure/language as the existing descriptions), "
        "\"tags\" (list of 10-15 tags, no hashtags), "
        "\"playlist\" (best matching existing playlist title, or a short new playlist name, or empty string)."
    ) % (
        channel, settings.get("style_hint", ""), os.path.basename(path), ex_block, len(taken),
        "\n".join("- " + t for t in sorted(taken)[:60]) or "(none)", json.dumps(playlists, ensure_ascii=False),
    )
    out = llm_json(prompt) or {}
    titles = [t.strip() for t in (out.get("titles") or []) if isinstance(t, str) and t.strip()]
    titles = [t[:100] for t in titles if is_unique(t, taken)]
    if not titles:
        titles = [fallback_title(channel, path, taken)]
    description = (out.get("description") or "").strip()
    if not description:
        description = "%s\n\nSubscribe for more." % titles[0]
    footer = (settings.get("desc_footer") or "").strip()
    if footer and footer not in description:
        description = description.rstrip() + "\n\n" + footer
    tags = [t.strip().lstrip("#") for t in (out.get("tags") or []) if isinstance(t, str) and t.strip()]
    for t in [x.strip() for x in (settings.get("default_tags") or "").split(",") if x.strip()]:
        if t.lower() not in {x.lower() for x in tags}:
            tags.append(t)
    tags = trim_tags(tags)
    playlist = (out.get("playlist") or "").strip()
    slot = row["publish_at"] or (next_free_slots(channel, 1) or [None])[0]
    with DBLOCK:
        con = db()
        con.execute(
            "UPDATE up_items SET title=?, description=?, tags=?, playlist=?, publish_at=?, suggestions=?, "
            "status=CASE WHEN status='new' THEN 'ready' ELSE status END, updated_at=? WHERE id=?",
            (titles[0], description[:5000], ", ".join(tags), playlist, slot, json.dumps(titles), iso(utcnow()), item_id),
        )
        con.commit()
        con.close()


def trim_tags(tags, budget=450):
    """YouTube limit is 500 chars across all tags; stay safely below."""
    out, used = [], 0
    for t in tags:
        cost = len(t) + (3 if " " in t else 1)
        if used + cost > budget:
            break
        out.append(t)
        used += cost
    return out


# ---------------------------------------------------------------- upload
def resumable_upload(channel, row, progress_cb):
    path = row["path"]
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    settings = channel_settings(channel)
    tags = [t.strip() for t in (row["tags"] or "").split(",") if t.strip()]
    status = {
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": bool(settings.get("made_for_kids")),
    }
    if row["publish_at"]:
        status["publishAt"] = row["publish_at"]
    meta = {
        "snippet": {
            "title": (row["title"] or "")[:100],
            "description": row["description"] or "",
            "tags": tags,
            "categoryId": str(settings.get("category") or "10"),
        },
        "status": status,
    }
    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode("utf-8"), method="POST")
    init_req.add_header("Authorization", "Bearer " + access_token(channel))
    init_req.add_header("Content-Type", "application/json; charset=UTF-8")
    init_req.add_header("X-Upload-Content-Length", str(size))
    init_req.add_header("X-Upload-Content-Type", mime)
    try:
        with urllib.request.urlopen(init_req, timeout=60) as res:
            session = res.headers.get("Location")
    except urllib.error.HTTPError as err:
        raise RuntimeError("YouTube init %s: %s" % (err.code, err.read().decode("utf-8", "replace")[:400]))
    if not session:
        raise RuntimeError("Το YouTube δεν έδωσε upload session.")
    chunk = 8 * 1024 * 1024         # multiple of 256 KiB
    sent = 0
    with open(path, "rb") as fh:
        while sent < size:
            fh.seek(sent)
            data = fh.read(chunk)
            end = sent + len(data) - 1
            req = urllib.request.Request(session, data=data, method="PUT")
            req.add_header("Content-Length", str(len(data)))
            req.add_header("Content-Range", "bytes %d-%d/%d" % (sent, end, size))
            try:
                with urllib.request.urlopen(req, timeout=300) as res:
                    body = json.loads(res.read().decode("utf-8") or "{}")
                    progress_cb(1.0)
                    return body.get("id")
            except urllib.error.HTTPError as err:
                if err.code == 308:
                    rng = err.headers.get("Range") or ""
                    sent = int(rng.split("-")[-1]) + 1 if "-" in rng else sent + len(data)
                    progress_cb(sent / float(size))
                    continue
                raise RuntimeError("YouTube upload %s: %s" % (err.code, err.read().decode("utf-8", "replace")[:400]))
    raise RuntimeError("Upload ended without a video id.")


def set_status(item_id, **fields):
    fields["updated_at"] = iso(utcnow())
    cols = ", ".join("%s=?" % k for k in fields)
    with DBLOCK:
        con = db()
        con.execute("UPDATE up_items SET %s WHERE id=?" % cols, list(fields.values()) + [item_id])
        con.commit()
        con.close()


def process_one():
    with DBLOCK:
        con = db()
        row = con.execute(
            "SELECT * FROM up_items WHERE status='approved' ORDER BY publish_at, id LIMIT 1").fetchone()
        con.close()
    if not row:
        return False
    item_id, channel = row["id"], row["channel"]
    try:
        if not ready(channel):
            raise RuntimeError("Λείπει το YouTube token για αυτό το κανάλι.")
        if os.path.splitext(row["path"])[1].lower() in AUDIO_EXT:
            raise RuntimeError("Το YouTube δέχεται μόνο βίντεο. Φτιάξε πρώτα βίντεο (π.χ. με το Beat Video Maker).")
        set_status(item_id, status="uploading", progress=0.0, error=None)
        vid = resumable_upload(channel, row, lambda p: set_status(item_id, progress=round(p, 3)))
        playlist_note = ""
        if row["playlist"]:
            try:
                add_to_playlist(channel, ensure_playlist(channel, row["playlist"]), vid)
            except Exception as err:
                playlist_note = "Ανέβηκε, αλλά το playlist απέτυχε: %s" % err
        with DBLOCK:
            con = db()
            con.execute("INSERT OR IGNORE INTO up_titles (channel, title) VALUES (?, ?)", (channel, row["title"]))
            con.commit()
            con.close()
        set_status(item_id, status="done", video_id=vid, progress=1.0, error=playlist_note or None)
        _CATALOG.pop(channel, None)
        archive_file(row["path"], channel)
    except Exception as err:
        traceback.print_exc()
        set_status(item_id, status="error", error=str(err)[:500])
    return True


def archive_file(path, channel):
    try:
        done_dir = os.path.join(INBOX, channel, "_done")
        os.makedirs(done_dir, exist_ok=True)
        os.replace(path, os.path.join(done_dir, os.path.basename(path)))
    except OSError:
        pass


def worker_loop():
    last_scan = 0.0
    while True:
        try:
            if time.time() - last_scan > 30:
                for ch in CHANNEL_IDS:
                    scan(ch)
                last_scan = time.time()
            busy = process_one()
        except Exception:
            traceback.print_exc()
            busy = False
        time.sleep(2 if busy else 10)


# ---------------------------------------------------------------- api
def row_view(row):
    item = dict(row)
    item["path"] = os.path.basename(row["path"])
    item["tags"] = row["tags"] or ""
    try:
        item["suggestions"] = json.loads(row["suggestions"] or "[]")
    except Exception:
        item["suggestions"] = []
    item["audio"] = os.path.splitext(row["path"])[1].lower() in AUDIO_EXT
    return item


def overview(channel):
    if channel not in CHANNEL_IDS:
        raise ValueError("Άγνωστο κανάλι.")
    scan(channel)
    with DBLOCK:
        con = db()
        rows = con.execute(
            "SELECT * FROM up_items WHERE channel=? AND status != 'skipped' ORDER BY "
            "CASE status WHEN 'uploading' THEN 0 WHEN 'approved' THEN 1 WHEN 'ready' THEN 2 WHEN 'new' THEN 3 "
            "WHEN 'error' THEN 4 ELSE 5 END, COALESCE(publish_at, '9'), id DESC LIMIT 200", (channel,)).fetchall()
        con.close()
    return {
        "channel": channel,
        "ready": ready(channel),
        "inbox": os.path.join(INBOX, channel),
        "llm": "anthropic" if ANTHROPIC_KEY else "ollama",
        "settings": channel_settings(channel),
        "items": [row_view(r) for r in rows],
    }


def handle_get(path, query):
    if path == "/api/uploader":
        return overview((query.get("channel") or [""])[0])
    if path == "/api/uploader/playlists":
        ch = (query.get("channel") or [""])[0]
        return {"playlists": list_playlists(ch)}
    return None


def _item(item_id):
    with DBLOCK:
        con = db()
        row = con.execute("SELECT * FROM up_items WHERE id=?", (item_id,)).fetchone()
        con.close()
    if not row:
        raise ValueError("Δεν βρέθηκε.")
    return row


def handle_post(path, body):
    def g(key, default=""):
        val = body.get(key, default)
        return val[0] if isinstance(val, list) and val else val

    if path == "/api/uploader/suggest":
        row = _item(int(g("id")))
        if row["status"] in ("approved", "uploading", "done"):
            raise ValueError("Έχει ήδη εγκριθεί.")
        suggest(row["id"], avoid=[g("avoid")] if g("avoid") else ())
        return {"ok": True}
    if path == "/api/uploader/suggest-all":
        ch = g("channel")
        with DBLOCK:
            con = db()
            ids = [r["id"] for r in con.execute(
                "SELECT id FROM up_items WHERE channel=? AND status='new' ORDER BY id", (ch,))]
            con.close()
        threading.Thread(target=lambda: [_safe(suggest, i) for i in ids], daemon=True).start()
        return {"ok": True, "count": len(ids)}
    if path == "/api/uploader/save":
        row = _item(int(g("id")))
        if row["status"] in ("approved", "uploading", "done"):
            raise ValueError("Δεν αλλάζει μετά το upload.")
        title = str(g("title")).strip()[:100]
        publish_at = str(g("publish_at")).strip() or None
        if publish_at:
            parse_iso(publish_at)
        set_status(row["id"], title=title, description=str(g("description"))[:5000],
                   tags=", ".join(trim_tags([t.strip() for t in str(g("tags")).split(",") if t.strip()])),
                   playlist=str(g("playlist")).strip(), publish_at=publish_at,
                   status="ready" if title else "new")
        return {"ok": True}
    if path == "/api/uploader/approve":
        row = _item(int(g("id")))
        if not (row["title"] or "").strip():
            raise ValueError("Βάλε τίτλο πρώτα.")
        if not is_unique(row["title"], {t for t in used_titles(row["channel"])} - {row["title"]}):
            raise ValueError("Ο τίτλος μοιάζει πολύ με υπάρχον βίντεο. Άλλαξέ τον.")
        set_status(row["id"], status="approved", error=None)
        return {"ok": True}
    if path == "/api/uploader/unapprove":
        row = _item(int(g("id")))
        if row["status"] == "approved":
            set_status(row["id"], status="ready")
        return {"ok": True}
    if path == "/api/uploader/skip":
        row = _item(int(g("id")))
        if row["status"] in ("uploading", "done"):
            raise ValueError("Δεν γίνεται τώρα.")
        try:
            skipped = os.path.join(INBOX, row["channel"], "_skipped")
            os.makedirs(skipped, exist_ok=True)
            os.replace(row["path"], os.path.join(skipped, os.path.basename(row["path"])))
        except OSError:
            pass
        set_status(row["id"], status="skipped")
        return {"ok": True}
    if path == "/api/uploader/retry":
        row = _item(int(g("id")))
        if row["status"] == "error":
            set_status(row["id"], status="ready", error=None)
        return {"ok": True}
    if path == "/api/uploader/reslot":
        ch = g("channel")
        with DBLOCK:
            con = db()
            ids = [r["id"] for r in con.execute(
                "SELECT id FROM up_items WHERE channel=? AND status IN ('new','ready') ORDER BY id", (ch,))]
            con.close()
        slots, taken = [], set()
        for _ in ids:
            nxt = next_free_slots(ch, 1, skip=taken)
            if not nxt:
                break
            slots.append(nxt[0])
            taken.add(nxt[0][:13])
        for i, slot in zip(ids, slots):
            set_status(i, publish_at=slot)
        return {"ok": True}
    if path == "/api/uploader/settings":
        ch = g("channel")
        if ch not in CHANNEL_IDS:
            raise ValueError("Άγνωστο κανάλι.")
        return {"settings": save_settings(ch, body)}
    return None


def _safe(fn, *a):
    try:
        fn(*a)
    except Exception:
        traceback.print_exc()
