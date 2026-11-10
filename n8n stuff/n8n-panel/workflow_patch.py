"""Add manual webhooks to the four YouTube workflows without replacing the rest of the graph.

RSS keeps its current path. A missing `platforms` list means all platforms, so new uploads
behave as they do today. The false branch of each platform gate still reaches Join IG Buffer,
because that merge waits for both inputs before it deletes the temporary reel.
"""
import json

from captions import n8n_fb_expr, n8n_short_desc_expr, n8n_short_title_expr, n8n_social_expr

CRED_NAME = "n8n panel webhook"
HEADER = "X-Panel-Token"

FILES = {
    "YouTube to Facebook Instagram TikTok - mrbonzomusic": "ui-import-mrbonzomusic.json",
    "YouTube to Facebook Instagram TikTok - mrbonzobeats": "ui-import-mrbonzobeats.json",
    "YouTube Short from long video - mrbonzomusic": "ui-import-short-mrbonzomusic.json",
    "YouTube Short from long video - mrbonzobeats": "ui-import-short-mrbonzobeats.json",
    "Story clip - mrbonzomusic": "ui-import-story-mrbonzomusic.json",
    "Story clip - mrbonzobeats": "ui-import-story-mrbonzobeats.json",
}

SPECS = {
    "YouTube to Facebook Instagram TikTok - mrbonzomusic": {
        "kind": "post",
        "channel": "mrbonzomusic",
        "path": "post-mrbonzomusic",
        "webhook": "Manual post mrbonzomusic",
        "format": "Format mrbonzomusic",
        "pack": "Pack music",
        "if_short": "If Short music",
        "check_short": "Check Short music",
        "upload": "Upload R2",
        "ig": "Instagram create",
        "tt": "Buffer TikTok",
        "join": "Join IG Buffer",
        "fb": ["Facebook Mr Bonzo"],
        "ig_prep": "IG Prep",
        "label": "Mr. Bonzo Music",
    },
    "YouTube to Facebook Instagram TikTok - mrbonzobeats": {
        "kind": "post",
        "channel": "mrbonzobeats",
        "path": "post-mrbonzobeats",
        "webhook": "Manual post mrbonzobeats",
        "format": "Format mrbonzobeats",
        "pack": "Pack beats",
        "if_short": "If Short beats",
        "check_short": "Check Short beats",
        "upload": "Upload R2",
        "ig": "Instagram create",
        "tt": "Buffer TikTok",
        "join": "Join IG Buffer",
        "fb": ["Facebook Mr Bonzo"],
        "ig_prep": "IG Prep",
        "label": "Mr. Bonzo Beats",
    },
    "YouTube Short from long video - mrbonzomusic": {
        "kind": "short",
        "channel": "mrbonzomusic",
        "path": "short-mrbonzomusic",
        "webhook": "Manual short mrbonzomusic",
        "format": "Format mrbonzomusic",
        "pack": "Pack music",
        "check_short": "Check Short music",
        "settings": "Settings",
        "wait": "Wait days",
        "make": "Make Short clip",
        "hook": "NEW MUSIC ♪",
        "cta": "Full video on the channel ▶",
    },
    "YouTube Short from long video - mrbonzobeats": {
        "kind": "short",
        "channel": "mrbonzobeats",
        "path": "short-mrbonzobeats",
        "webhook": "Manual short mrbonzobeats",
        "format": "Format mrbonzobeats",
        "pack": "Pack beats",
        "check_short": "Check Short beats",
        "settings": "Settings",
        "wait": "Wait days",
        "make": "Make Short clip",
        "hook": "NEW BEAT ♪",
        "cta": "Full beat on the channel ▶",
    },
    "Story clip - mrbonzomusic": {
        "kind": "story",
        "channel": "mrbonzomusic",
        "path": "story-mrbonzomusic",
        "webhook": "Manual story mrbonzomusic",
        "hook": "MR. BONZO ♪",
        "rssHook": "NEW MUSIC ♪",
        "feed": "UCAPju2g7sZ4z0qwMhrkhYng",
        "cta": "Link in bio ▶",
    },
    "Story clip - mrbonzobeats": {
        "kind": "story",
        "channel": "mrbonzobeats",
        "path": "story-mrbonzobeats",
        "webhook": "Manual story mrbonzobeats",
        "hook": "TYPE BEAT ♪",
        "rssHook": "NEW BEAT ♪",
        "feed": "UCLzRHkxvT9HBMjNPI7L31ZQ",
        "cta": "Link in bio ▶",
    },
}

SENSITIVE = (
    "n8n-nodes-base.facebookGraphApi",
    "n8n-nodes-base.s3",
    "@bufferapp/n8n-nodes-buffer.buffer",
)


def platform_expr(pack, test):
    return (
        "={{ (() => { const p = $('%s').item.json.platforms; "
        "if (p == null || p === '' || (Array.isArray(p) && p.length === 0)) return true; "
        "const list = Array.isArray(p) ? p.map(String) : String(p).split(','); "
        "return %s; })() }}"
    ) % (pack, test)


def prefer(expr, field):
    if "$json.%s ||" % field in expr:
        return expr
    if not (expr.startswith("={{") and expr.endswith("}}")):
        return expr
    inner = expr[3:-2].strip()
    return "={{ $json.%s || (%s) }}" % (field, inner)


def node_by(wf, name):
    for node in wf.get("nodes") or []:
        if node.get("name") == name:
            return node
    raise KeyError(name)


def assignments(node):
    return node["parameters"]["assignments"]["assignments"]


def ensure_assignment(node, name, value, typ):
    for item in assignments(node):
        if item.get("name") == name:
            changed = item.get("value") != value or item.get("type") != typ
            item["value"] = value
            item["type"] = typ
            return changed
    assignments(node).append({"id": "panel-%s" % name, "name": name, "value": value, "type": typ})
    return True


def edge(name, index=0):
    return {"node": name, "type": "main", "index": index}


def set_main(wf, src, groups):
    """groups is a list of output branches. Each branch is a list of edge dicts."""
    wf.setdefault("connections", {})
    wf["connections"][src] = {"main": [list(group) for group in groups]}


def upsert(wf, fresh):
    for node in wf["nodes"]:
        if node.get("name") == fresh["name"]:
            keep = node.get("credentials") if fresh.get("type") == "n8n-nodes-base.webhook" and "credentials" not in fresh else None
            node["type"] = fresh["type"]
            node["typeVersion"] = fresh["typeVersion"]
            node["parameters"] = fresh["parameters"]
            if "credentials" in fresh:
                node["credentials"] = fresh["credentials"]
            elif keep:
                node["credentials"] = keep
                node["parameters"]["authentication"] = "headerAuth"
            elif fresh.get("type") == "n8n-nodes-base.webhook":
                node.pop("credentials", None)
            if "notes" in fresh:
                node["notes"] = fresh["notes"]
            if "onError" in fresh:
                node["onError"] = fresh["onError"]
            if "position" in fresh:
                node["position"] = fresh["position"]
            return node, False
    wf["nodes"].append(fresh)
    return fresh, True


def is_short_expr(format_name):
    return (
        "={{ (() => { "
        "const title = String($('%s').item.json.title || ''); "
        "const link = String($('%s').item.json.link || ''); "
        "if (title.toLowerCase().includes('#shorts') || link.includes('/shorts/')) return true; "
        "let dur = null; "
        "try { const info = $('Video info').item.json || {}; dur = Number(info.durationSeconds || info.duration); } catch (e) { dur = null; } "
        "if (Number.isFinite(dur) && dur > 0) return dur <= 60; "
        "const h = $json.headers || {}; const loc = String(h.location || h.Location || ''); "
        "const url = String($json.url || ''); "
        "if (loc.includes('/watch')) return false; "
        "if (loc.includes('/shorts/') || url.includes('/shorts/')) return true; "
        "return Number($json.statusCode) === 200; })() }}"
    ) % (format_name, format_name)


def skip_short_node(channel, position):
    return {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "skip-short-flag", "name": "skipped", "value": "short", "type": "string"}
                ]
            },
            "options": {},
        },
        "id": "skip-short-" + channel,
        "name": "Skip Short social",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": position,
        "notes": "YouTube Shorts δεν πάνε σε Facebook, Instagram, TikTok ή Plunk.",
    }


def plunk_gate_expr():
    return (
        "={{ (() => { const id = String($json.requestId || ''); "
        "const key = String($env.PLUNK_SECRET_KEY || ''); "
        "const from = String($env.PLUNK_FROM_EMAIL || ''); "
        "return id === '' && key !== '' && from !== ''; })() }}"
    )


def plunk_create_node(spec, position):
    label = spec.get("label") or spec["channel"]
    body = (
        "={{ JSON.stringify((() => { "
        "const title = String($json.title || 'New video'); "
        "const link = String($json.link || ''); "
        "const vid = String($json.videoId || ((link.match(/[?&]v=([^&]+)/) || link.match(/\\/shorts\\/([^/?]+)/) || [null,''])[1] || '')); "
        "const thumb = vid ? ('https://i.ytimg.com/vi/' + vid + '/hqdefault.jpg') : ''; "
        "const html = '<div style=\"font-family:system-ui,sans-serif;max-width:560px;margin:0 auto;color:#111\">'"
        " + '<p style=\"color:#666;font-size:13px;margin:0 0 8px\">' + %s + '</p>'"
        " + '<h1 style=\"font-size:22px;line-height:1.3;margin:0 0 16px\">' + title.replace(/</g,'&lt;') + '</h1>'"
        " + (thumb ? ('<p><a href=\"' + link + '\"><img src=\"' + thumb + '\" alt=\"' + title.replace(/\"/g,'') + '\" width=\"560\" style=\"width:100%%;max-width:560px;border-radius:12px\"></a></p>') : '')"
        " + '<p style=\"color:#666;font-size:13px\">Watch on YouTube</p>'"
        " + '<p><a href=\"' + link + '\" style=\"display:inline-block;background:#7c5cbf;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:600\">Watch on YouTube</a></p>'"
        " + '<p style=\"margin-top:16px\"><a href=\"https://mrbonzo-beats.pages.dev/\" style=\"color:#7c5cbf\">mrbonzo-beats.pages.dev</a></p>'"
        " + '</div>'; "
        "return { name: 'YouTube · ' + title.slice(0, 80), subject: title.slice(0, 120), "
        "body: html, from: $env.PLUNK_FROM_EMAIL, fromName: %s, audienceType: 'ALL' }; })()) }}"
    ) % (js_string(label), js_string(label))
    return {
        "parameters": {
            "method": "POST",
            "url": "http://plunk:8080/v1/campaigns",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.PLUNK_SECRET_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body,
            "options": {},
        },
        "id": "plunk-create-" + spec["channel"],
        "name": "Plunk create campaign",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "onError": "continueRegularOutput",
        "notes": "RSS long video μόνο. Το secret είναι env στο n8n, όχι στο workflow JSON.",
    }


def plunk_send_node(channel, position):
    return {
        "parameters": {
            "method": "POST",
            "url": "=http://plunk:8080/v1/campaigns/{{ ($json.data && $json.data.id) || $json.id }}/send",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.PLUNK_SECRET_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ scheduledFor: null }) }}",
            "options": {},
        },
        "id": "plunk-send-" + channel,
        "name": "Plunk send campaign",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "onError": "continueRegularOutput",
    }


def if_node(name, node_id, left, position):
    return {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": node_id + "-c",
                        "leftValue": left,
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            }
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
    }


def code_node(name, node_id, js, position, notes=""):
    node = {
        "parameters": {"jsCode": js},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
    }
    if notes:
        node["notes"] = notes
    return node


def http_get_node(name, node_id, url, position, timeout=20000):
    return {
        "parameters": {
            "method": "GET",
            "url": url,
            "options": {
                "timeout": timeout,
                "response": {"response": {"neverError": True}},
            },
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    }


def retry_node(node, tries=3, wait=4000):
    if node.get("type") in (
        "n8n-nodes-base.facebookGraphApi",
        "n8n-nodes-base.s3",
        "n8n-nodes-base.httpRequest",
        "@bufferapp/n8n-nodes-buffer.buffer",
    ):
        node["retryOnFail"] = True
        node["maxTries"] = tries
        node["waitBetweenTries"] = wait
    return node


def apply_retries(wf):
    skip = {"Video info", "Check Short music", "Check Short beats", "Cleanup local", "Plunk send campaign"}
    for node in wf.get("nodes") or []:
        if node.get("name") in skip:
            continue
        retry_node(node)


def video_info_node(channel, format_name, position):
    url = (
        "={{ 'http://n8n-reels:8080/info?videoId=' + encodeURIComponent("
        "(($('%s').item.json.link || '').match(/[?&]v=([^&]+)/) "
        "|| ($('%s').item.json.link || '').match(/\\/shorts\\/([^/?]+)/) || [null,''])[1] || '') }}"
    ) % (format_name, format_name)
    return http_get_node("Video info", "video-info-" + channel, url, position)


def dedup_js(kind):
    return (
        "const kind = %s;\n"
        "const j = $input.first().json || {};\n"
        "const videoId = String(j.videoId || '');\n"
        "const requestId = String(j.requestId || '');\n"
        "const staticData = $getWorkflowStaticData('global');\n"
        "staticData[kind] = staticData[kind] || {};\n"
        "let skipped = '';\n"
        "if (videoId && !requestId && staticData[kind][videoId]) skipped = 'duplicate';\n"
        "return [{ json: { ...j, skipped } }];\n"
    ) % json.dumps(kind)


def remember_js(kind, pack):
    return (
        "const kind = %s;\n"
        "const j = $input.first().json || {};\n"
        "let videoId = String(j.videoId || '');\n"
        "try { videoId = videoId || String($(%s).first().json.videoId || ''); } catch (e) {}\n"
        "const staticData = $getWorkflowStaticData('global');\n"
        "staticData[kind] = staticData[kind] || {};\n"
        "if (videoId) staticData[kind][videoId] = Date.now();\n"
        "return [{ json: { ...j, videoId, remembered: true } }];\n"
    ) % (json.dumps(kind), json.dumps(pack))


def ig_status_js():
    return (
        "const raw = $input.first().json || {};\n"
        "const code = String(raw.status_code || '').toUpperCase();\n"
        "if (code === 'ERROR' || raw.error) {\n"
        "  throw new Error('Instagram media ERROR: ' + JSON.stringify(raw).slice(0, 400));\n"
        "}\n"
        "return [{ json: { ...raw, igReady: code === 'FINISHED' } }];\n"
    )


def ig_failed_js():
    return (
        "const raw = $input.first().json || {};\n"
        "throw new Error('Instagram reel not FINISHED: ' + String(raw.status_code || 'unknown'));\n"
    )


def check_social_js(pack):
    return (
        "function ran(name) { try { return $(name).all(); } catch (e) { return null; } }\n"
        "function failed(items) {\n"
        "  if (!items) return true;\n"
        "  for (const item of items) {\n"
        "    const j = item.json || {};\n"
        "    if (j.error || (item.error && item.error.message)) return true;\n"
        "  }\n"
        "  return false;\n"
        "}\n"
        "const pack = $(%s).first().json;\n"
        "const p = pack.platforms;\n"
        "const all = p == null || p === '' || (Array.isArray(p) && p.length === 0);\n"
        "const want = (n) => all || (Array.isArray(p) && p.map(String).includes(n));\n"
        "const fails = [];\n"
        "if (want('instagram')) {\n"
        "  const items = ran('Instagram publish');\n"
        "  if (!items || failed(items)) fails.push('instagram');\n"
        "}\n"
        "if (want('tiktok')) {\n"
        "  const items = ran('Buffer TikTok');\n"
        "  if (!items || failed(items)) fails.push('tiktok');\n"
        "}\n"
        "if (fails.length) throw new Error('Social post failed: ' + fails.join(', '));\n"
        "return [{ json: { socialOk: true, videoId: pack.videoId } }];\n"
    ) % json.dumps(pack)


def set_wait_amount(wf, name, amount, unit="seconds"):
    try:
        node = node_by(wf, name)
    except KeyError:
        return False
    node.setdefault("parameters", {})
    node["parameters"]["amount"] = amount
    node["parameters"]["unit"] = unit
    return True


def set_query_param(node, key, value):
    params = (((node.get("parameters") or {}).get("options") or {}).get("queryParameters") or {}).get("parameter") or []
    changed = False
    for item in params:
        if item.get("name") == key:
            if item.get("value") != value:
                item["value"] = value
                changed = True
    return changed


def webhook_node(spec, cred):
    params = {
        "httpMethod": "POST",
        "path": spec["path"],
        "responseMode": "onReceived",
        "options": {},
    }
    node = {
        "parameters": params,
        "id": "wh-" + spec["path"],
        "name": spec["webhook"],
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [-280, 280],
        "webhookId": spec["path"],
        "notes": "Το panel στέλνει εδώ ένα παλιό ή επιλεγμένο βίντεο. Το RSS δεν περνάει από αυτόν τον κόμβο.",
    }
    if cred and cred.get("id"):
        params["authentication"] = "headerAuth"
        node["credentials"] = {"httpHeaderAuth": {"id": cred["id"], "name": cred.get("name") or CRED_NAME}}
    else:
        params["authentication"] = "none"
    return node


def normalize_node(spec):
    rows = [
        ("title", "={{ ($json.body && $json.body.title) || '' }}", "string"),
        ("link", "={{ ($json.body && $json.body.link) || ('https://www.youtube.com/watch?v=' + (($json.body && $json.body.videoId) || '')) }}", "string"),
        ("requestId", "={{ ($json.body && $json.body.requestId) || '' }}", "string"),
    ]
    if spec["kind"] == "post":
        rows.append(("message", "={{ ($json.body && $json.body.message) || '' }}", "string"))
        rows.append(("messageFb", "={{ ($json.body && ($json.body.messageFb || $json.body.message)) || '' }}", "string"))
        rows.append(("messageSocial", "={{ ($json.body && $json.body.messageSocial) || '' }}", "string"))
        rows.append(("platforms", "={{ ($json.body && $json.body.platforms) || null }}", "array"))
    else:
        rows.extend([
            ("shortTitle", "={{ ($json.body && $json.body.shortTitle) || '' }}", "string"),
            ("shortDescription", "={{ ($json.body && $json.body.shortDescription) || '' }}", "string"),
            ("skipWait", "={{ true }}", "boolean"),
            ("clipStart", "={{ ($json.body && ($json.body.start || $json.body.clipStart)) || 'auto' }}", "string"),
            ("clipSeconds", "={{ Number(($json.body && ($json.body.seconds || $json.body.clipSeconds)) || 30) }}", "number"),
            ("hookSet", "={{ true }}", "boolean"),
            ("ctaSet", "={{ true }}", "boolean"),
            ("hookText", "={{ ($json.body && $json.body.hook != null) ? $json.body.hook : (($json.body && $json.body.hookText != null) ? $json.body.hookText : '') }}", "string"),
            ("ctaText", "={{ ($json.body && $json.body.cta != null) ? $json.body.cta : (($json.body && $json.body.ctaText != null) ? $json.body.ctaText : '') }}", "string"),
        ])
    return {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "norm-%s" % name, "name": name, "value": value, "type": typ}
                    for name, value, typ in rows
                ]
            },
            "includeOtherFields": False,
            "options": {},
        },
        "id": "norm-" + spec["path"],
        "name": "Manual normalize",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-40, 280],
    }


def copy_pack(pack, format_name, field, typ):
    return ensure_assignment(pack, field, "={{ $('%s').item.json.%s }}" % (format_name, field), typ)


def patch_post(wf, spec, cred):
    changed = False
    hook, added = upsert(wf, webhook_node(spec, cred))
    changed = changed or added or hook.get("parameters", {}).get("path") == spec["path"]
    norm, added = upsert(wf, normalize_node(spec))
    changed = changed or added
    fmt = node_by(wf, spec["format"])
    pack = node_by(wf, spec["pack"])
    if ensure_assignment(fmt, "messageFb", n8n_fb_expr(spec["channel"]), "string"):
        changed = True
    if ensure_assignment(fmt, "messageSocial", n8n_social_expr(spec["channel"]), "string"):
        changed = True
    if ensure_assignment(fmt, "platforms", "={{ $json.platforms }}", "array"):
        changed = True
    if ensure_assignment(fmt, "requestId", "={{ $json.requestId || '' }}", "string"):
        changed = True
    for field, typ in (
        ("platforms", "array"),
        ("requestId", "string"),
        ("messageFb", "string"),
        ("messageSocial", "string"),
    ):
        if copy_pack(pack, spec["format"], field, typ):
            changed = True
    if ensure_assignment(pack, "isShort", is_short_expr(spec["format"]), "boolean"):
        changed = True
    if ensure_assignment(
        pack, "durationSeconds",
        "={{ (() => { try { const n = Number(($('Video info').item.json.durationSeconds || $('Video info').item.json.duration)); return Number.isFinite(n) ? n : 0; } catch (e) { return 0; } })() }}",
        "number",
    ):
        changed = True

    base = node_by(wf, spec["if_short"]).get("position") or [960, 0]
    skip, added = upsert(wf, skip_short_node(spec["channel"], [base[0] + 220, base[1] - 280]))
    changed = changed or added
    gate_fb, added = upsert(wf, if_node(
        "Gate Facebook", "gate-fb-" + spec["channel"],
        platform_expr(spec["pack"], "list.includes('facebook')"),
        [base[0] + 220, base[1] - 140],
    ))
    changed = changed or added
    gate_reel, added = upsert(wf, if_node(
        "Gate Reel", "gate-reel-" + spec["channel"],
        platform_expr(spec["pack"], "list.includes('instagram') || list.includes('tiktok')"),
        [base[0] + 220, base[1] + 140],
    ))
    changed = changed or added
    gate_plunk, added = upsert(wf, if_node(
        "Gate Plunk", "gate-plunk-" + spec["channel"],
        plunk_gate_expr(),
        [base[0] + 220, base[1] + 300],
    ))
    changed = changed or added
    plunk_create, added = upsert(wf, plunk_create_node(spec, [base[0] + 460, base[1] + 300]))
    changed = changed or added
    plunk_send, added = upsert(wf, plunk_send_node(spec["channel"], [base[0] + 920, base[1] + 300]))
    changed = changed or added
    gate_plunk_send, added = upsert(wf, if_node(
        "Gate Plunk send", "gate-plunk-send-" + spec["channel"],
        "={{ String($env.PLUNK_AUTO_SEND || '').toLowerCase() === 'true' }}",
        [base[0] + 700, base[1] + 300],
    ))
    changed = changed or added
    fmt_pos = fmt.get("position") or [240, 0]
    info, added = upsert(wf, video_info_node(spec["channel"], spec["format"], [fmt_pos[0] + 180, fmt_pos[1] + 160]))
    changed = changed or added
    pack_pos = pack.get("position") or [720, 0]
    _, added = upsert(wf, code_node(
        "RSS dedup", "rss-dedup-" + spec["channel"], dedup_js("post"),
        [pack_pos[0] + 160, pack_pos[1]], "Skip RSS if this videoId already posted.",
    ))
    changed = changed or added
    _, added = upsert(wf, if_node(
        "If duplicate", "if-dup-" + spec["channel"],
        "={{ $json.skipped === 'duplicate' }}",
        [pack_pos[0] + 360, pack_pos[1]],
    ))
    changed = changed or added
    for letter, wait_name, poll_name, if_name in (
        ("A", "Wait IG A", "IG poll A", "If IG ready A"),
        ("B", "Wait IG B", "IG poll B", "If IG ready B"),
        ("C", "Wait IG C", "IG poll C", "If IG ready C"),
    ):
        try:
            pos = node_by(wf, poll_name).get("position") or [1840, 400]
        except KeyError:
            continue
        _, added = upsert(wf, code_node(
            "IG status " + letter, "ig-status-" + letter.lower() + "-" + spec["channel"],
            ig_status_js(), [pos[0] + 80, pos[1] + 20],
        ))
        changed = changed or added
        try:
            ready = node_by(wf, if_name)
            for cond in (((ready.get("parameters") or {}).get("conditions") or {}).get("conditions") or []):
                cond["leftValue"] = "={{ $json.igReady }}"
                cond["operator"] = {"type": "boolean", "operation": "equals"}
                cond["rightValue"] = True
        except KeyError:
            pass
    try:
        cpos = node_by(wf, "If IG ready C").get("position") or [1960, 640]
    except KeyError:
        cpos = [1960, 640]
    _, added = upsert(wf, code_node(
        "IG not ready", "ig-not-ready-" + spec["channel"], ig_failed_js(),
        [cpos[0] + 220, cpos[1] + 80],
    ))
    changed = changed or added
    join_pos = node_by(wf, spec["join"]).get("position") or [2440, 280]
    _, added = upsert(wf, code_node(
        "Check social", "check-social-" + spec["channel"], check_social_js(spec["pack"]),
        [join_pos[0] + 280, join_pos[1] - 40],
    ))
    changed = changed or added
    _, added = upsert(wf, code_node(
        "Remember post", "remember-post-" + spec["channel"], remember_js("post", spec["pack"]),
        [join_pos[0] + 500, join_pos[1] - 40],
    ))
    changed = changed or added
    _, added = upsert(wf, code_node(
        "Remember post FB", "remember-post-fb-" + spec["channel"], remember_js("post", spec["pack"]),
        [1720, -80],
    ))
    changed = changed or added
    set_wait_amount(wf, "Wait Buffer fetch", 180, "seconds")
    up = node_by(wf, spec["upload"]).get("position") or [1900, 200]
    gate_ig, added = upsert(wf, if_node(
        "Gate Instagram", "gate-ig-" + spec["channel"],
        platform_expr(spec["pack"], "list.includes('instagram')"),
        [up[0] + 220, up[1] - 80],
    ))
    changed = changed or added
    gate_tt, added = upsert(wf, if_node(
        "Gate TikTok", "gate-tt-" + spec["channel"],
        platform_expr(spec["pack"], "list.includes('tiktok')"),
        [up[0] + 220, up[1] + 80],
    ))
    changed = changed or added

    check_short = spec.get("check_short") or "Check Short music"
    set_main(wf, spec["webhook"], [[edge("Manual normalize")]])
    set_main(wf, "Manual normalize", [[edge(spec["format"])]])
    set_main(wf, spec["format"], [[edge("Video info")]])
    set_main(wf, "Video info", [[edge(check_short)]])
    set_main(wf, spec["pack"], [[edge("RSS dedup")]])
    set_main(wf, "RSS dedup", [[edge("If duplicate")]])
    set_main(wf, "If duplicate", [[], [edge(spec["if_short"])]])
    set_main(wf, spec["if_short"], [[edge("Skip Short social")], [edge("Gate Facebook"), edge("Gate Reel"), edge("Gate Plunk")]])
    set_main(wf, "Gate Facebook", [[edge(name) for name in spec["fb"]], []])
    set_main(wf, "Gate Reel", [[edge(spec["ig_prep"])], []])
    set_main(wf, "Gate Plunk", [[edge("Plunk create campaign")], []])
    set_main(wf, "Plunk create campaign", [[edge("Gate Plunk send")]])
    set_main(wf, "Gate Plunk send", [[edge("Plunk send campaign")], []])
    set_main(wf, spec["upload"], [[edge("Gate Instagram"), edge("Gate TikTok")]])
    set_main(wf, "Gate Instagram", [[edge(spec["ig"])], [edge(spec["join"], 0)]])
    set_main(wf, "Gate TikTok", [[edge(spec["tt"])], [edge(spec["join"], 1)]])
    for letter, poll_name, if_name in (
        ("A", "IG poll A", "If IG ready A"),
        ("B", "IG poll B", "If IG ready B"),
        ("C", "IG poll C", "If IG ready C"),
    ):
        set_main(wf, poll_name, [[edge("IG status " + letter)]])
        set_main(wf, "IG status " + letter, [[edge(if_name)]])
    set_main(wf, "If IG ready C", [[edge("Instagram publish")], [edge("IG not ready")]])
    set_main(wf, spec["join"], [[edge("Wait Buffer fetch")]])
    set_main(wf, "Wait Buffer fetch", [[edge("Check social")]])
    set_main(wf, "Check social", [[edge("Remember post")]])
    set_main(wf, "Remember post", [[edge("Delete R2")]])
    set_main(wf, "Check Facebook", [[edge("Remember post FB")]])
    try:
        ig_prep = node_by(wf, spec["ig_prep"])
        if ensure_assignment(ig_prep, "messageSocial", "={{ $json.messageSocial || $json.message }}", "string"):
            changed = True
        if ensure_assignment(ig_prep, "messageFb", "={{ $json.messageFb || $json.message }}", "string"):
            changed = True
    except KeyError:
        pass
    social_caption(wf)
    return True


def social_caption(wf):
    social = "={{ $('IG Prep').item.json.messageSocial || $('IG Prep').item.json.message || '' }}"
    fb_msg = "={{ $json.messageFb || $json.message }}"
    for node in wf.get("nodes") or []:
        params = node.setdefault("parameters", {})
        if node.get("name") == "Instagram create":
            for item in (((params.get("options") or {}).get("queryParameters") or {}).get("parameter") or []):
                if item.get("name") == "caption":
                    item["value"] = social
        elif node.get("name") == "Buffer TikTok":
            params["postText"] = social
        elif node.get("type") == "n8n-nodes-base.facebookGraphApi" and "Facebook" in (node.get("name") or ""):
            set_query_param(node, "message", fb_msg)


def js_string(text):
    return json.dumps(text, ensure_ascii=False)


def setting_expr(pack, field, fallback):
    return (
        "={{ (() => { const v = $('%s').item.json.%s; "
        "return (v === undefined || v === null || v === '') ? (%s) : v; })() }}"
    ) % (pack, field, fallback)


def patch_short(wf, spec, cred):
    hook, added = upsert(wf, webhook_node(spec, cred))
    norm, added_norm = upsert(wf, normalize_node(spec))
    fmt = node_by(wf, spec["format"])
    pack = node_by(wf, spec["pack"])
    changed = added or added_norm
    if ensure_assignment(fmt, "shortTitle", n8n_short_title_expr(spec["channel"]), "string"):
        changed = True
    if ensure_assignment(fmt, "shortDescription", n8n_short_desc_expr(spec["channel"]), "string"):
        changed = True
    for field, typ, value in (
        ("requestId", "string", "={{ $json.requestId || '' }}"),
        ("skipWait", "boolean", "={{ $json.skipWait === true }}"),
        ("clipStart", "string", "={{ $json.clipStart || '' }}"),
        ("clipSeconds", "string", "={{ ($json.clipSeconds === undefined || $json.clipSeconds === null || $json.clipSeconds === '') ? '' : String($json.clipSeconds) }}"),
        ("hookSet", "boolean", "={{ $json.hookSet === true }}"),
        ("ctaSet", "boolean", "={{ $json.ctaSet === true }}"),
        ("hookText", "string", "={{ $json.hookText || '' }}"),
        ("ctaText", "string", "={{ $json.ctaText || '' }}"),
    ):
        if ensure_assignment(fmt, field, value, typ):
            changed = True
    for field, typ in (
        ("requestId", "string"),
        ("skipWait", "boolean"),
        ("clipStart", "string"),
        ("clipSeconds", "string"),
        ("hookSet", "boolean"),
        ("ctaSet", "boolean"),
        ("hookText", "string"),
        ("ctaText", "string"),
    ):
        if copy_pack(pack, spec["format"], field, typ):
            changed = True
    if ensure_assignment(pack, "isShort", is_short_expr(spec["format"]), "boolean"):
        changed = True
    if copy_pack(pack, spec["format"], "shortTitle", "string"):
        changed = True
    if copy_pack(pack, spec["format"], "shortDescription", "string"):
        changed = True

    settings = node_by(wf, spec["settings"])
    pack_name = spec["pack"]
    wanted = {
        "delayDays": ("={{ $('%s').item.json.skipWait === true ? 0 : 3 }}" % pack_name, "number"),
        "clipStart": (setting_expr(pack_name, "clipStart", "'auto'"), "string"),
        "clipSeconds": (setting_expr(pack_name, "clipSeconds", "30"), "number"),
        "hookText": (
            "={{ $('%s').item.json.hookSet === true ? ($('%s').item.json.hookText || '') : %s }}"
            % (pack_name, pack_name, js_string(spec["hook"])),
            "string",
        ),
        "ctaText": (
            "={{ $('%s').item.json.ctaSet === true ? ($('%s').item.json.ctaText || '') : %s }}"
            % (pack_name, pack_name, js_string(spec["cta"])),
            "string",
        ),
        "skipWait": ("={{ $('%s').item.json.skipWait === true }}" % pack_name, "boolean"),
    }
    for item in assignments(settings):
        if item.get("name") in wanted:
            value, typ = wanted[item["name"]]
            if item.get("value") != value or item.get("type") != typ:
                item["value"] = value
                item["type"] = typ
                changed = True
    for name, (value, typ) in wanted.items():
        if ensure_assignment(settings, name, value, typ):
            changed = True

    base = settings.get("position") or [1200, 0]
    skip, added = upsert(wf, if_node(
        "Skip wait", "skip-wait-" + spec["channel"],
        "={{ $json.skipWait }}",
        [base[0] + 220, base[1]],
    ))
    changed = changed or added
    fmt_pos = fmt.get("position") or [240, 0]
    _, added = upsert(wf, video_info_node(spec["channel"], spec["format"], [fmt_pos[0] + 180, fmt_pos[1] + 160]))
    changed = changed or added
    pack_pos = pack.get("position") or [720, 0]
    _, added = upsert(wf, code_node(
        "RSS dedup", "rss-dedup-" + spec["channel"], dedup_js("short"),
        [pack_pos[0] + 160, pack_pos[1]],
    ))
    changed = changed or added
    _, added = upsert(wf, if_node(
        "If duplicate", "if-dup-" + spec["channel"],
        "={{ $json.skipped === 'duplicate' }}",
        [pack_pos[0] + 360, pack_pos[1]],
    ))
    changed = changed or added
    try:
        chk_pos = node_by(wf, "Check Buffer").get("position") or [3360, 0]
    except KeyError:
        chk_pos = [3360, 0]
    _, added = upsert(wf, code_node(
        "Remember short", "remember-short-" + spec["channel"], remember_js("short", spec["pack"]),
        [chk_pos[0] + 220, chk_pos[1]],
    ))
    changed = changed or added
    set_wait_amount(wf, "Wait Buffer fetch", 180, "seconds")
    check_short = spec.get("check_short") or "Check Short music"
    set_main(wf, spec["webhook"], [[edge("Manual normalize")]])
    set_main(wf, "Manual normalize", [[edge(spec["format"])]])
    set_main(wf, spec["format"], [[edge("Video info")]])
    set_main(wf, "Video info", [[edge(check_short)]])
    set_main(wf, spec["pack"], [[edge("RSS dedup")]])
    set_main(wf, "RSS dedup", [[edge("If duplicate")]])
    set_main(wf, "If duplicate", [[], [edge("Only long videos")]])
    set_main(wf, spec["settings"], [[edge("Skip wait")]])
    set_main(wf, "Skip wait", [[edge(spec["make"])], [edge(spec["wait"])]])
    set_main(wf, "Wait Buffer fetch", [[edge("Check Buffer")]])
    set_main(wf, "Check Buffer", [[edge("Remember short")]])
    set_main(wf, "Remember short", [[edge("Delete R2")]])
    set_main(wf, "Delete R2", [[edge("Cleanup local")]])
    set_main(wf, "Cleanup local", [[]])
    workflow_settings = wf.setdefault("settings", {})
    if not workflow_settings.get("executionTimeout") or int(workflow_settings.get("executionTimeout") or 0) < 0:
        workflow_settings["executionTimeout"] = 1800
    return changed or True


STORY_URL = "https://pub-1cb7f846eb8e4ab998a9cf2e22cc3c75.r2.dev/stories/"
STORY_IG = "17841404419062410"
STORY_FB = {"id": "HzmFdeNPMKO2sQtk", "name": "Facebook Mr Bonzo"}
STORY_S3 = {"id": "7uiqHIsogZqpfxT8", "name": "S3 account"}


def _story_graph(name, node_id, path, params, position, method="POST"):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 4000,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "graphApiVersion": "v21.0",
            "httpRequestMethod": method,
            "node": path,
            "options": {
                "queryParameters": {
                    "parameter": [{"name": key, "value": value} for key, value in params]
                }
            },
        },
        "credentials": {"facebookGraphApi": STORY_FB},
    }


def _story_wait(name, node_id, seconds, position):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "webhookId": node_id,
        "position": position,
        "parameters": {"amount": seconds},
    }


def _story_throw(name, node_id, message, position):
    node = code_node(name, node_id, "throw new Error(%s);" % json.dumps(message, ensure_ascii=False), position)
    node["parameters"]["mode"] = "runOnceForAllItems"
    node["parameters"]["language"] = "javaScript"
    return node


def patch_story(wf, spec, cred):
    """Replace the graph with a 30s vertical clip posted as an IG and Mr. Bonzo story."""
    channel = spec["channel"]
    url = "={{ '%s' + $('Story pack').item.json.videoId + '.mp4' }}" % STORY_URL
    seconds = (
        "={{ (() => { const raw = ($json.body && ($json.body.seconds || $json.body.clipSeconds)); "
        "const n = Number(raw); "
        "if (raw === undefined || raw === null || raw === '' || !Number.isFinite(n) || n > 60 || n < 5) return 30; "
        "return Math.round(n); })() }}"
    )
    start = (
        "={{ (() => { const s = String(($json.body && ($json.body.start || $json.body.clipStart)) || 'auto').trim(); "
        "return (s === 'auto' || /^[0-9]+$/.test(s)) ? s : 'auto'; })() }}"
    )
    hook = (
        "={{ ($json.body && $json.body.hook != null && String($json.body.hook) !== '') ? String($json.body.hook) : %s }}"
        % json.dumps(spec["hook"])
    )
    cta = (
        "={{ ($json.body && $json.body.cta != null && String($json.body.cta) !== '') ? String($json.body.cta) : %s }}"
        % json.dumps(spec["cta"])
    )
    rows = [
        ("videoId", "={{ ($json.body && $json.body.videoId) || '' }}", "string"),
        ("title", "={{ ($json.body && $json.body.title) || '' }}", "string"),
        ("requestId", "={{ ($json.body && $json.body.requestId) || '' }}", "string"),
        ("clipStart", start, "string"),
        ("clipSeconds", seconds, "number"),
        ("hookText", hook, "string"),
        ("ctaText", cta, "string"),
    ]
    normalize = {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "story-%s" % name, "name": name, "value": value, "type": typ}
                    for name, value, typ in rows
                ]
            },
            "includeOtherFields": False,
            "options": {},
        },
        "id": "norm-" + spec["path"],
        "name": "Manual normalize",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [0, 0],
    }
    clip_body = (
        "={{ JSON.stringify({ videoId: $('Story pack').item.json.videoId, "
        "start: String($('Story pack').item.json.clipStart || 'auto'), "
        "seconds: Number($('Story pack').item.json.clipSeconds), "
        "hook: $('Story pack').item.json.hookText || '', "
        "cta: $('Story pack').item.json.ctaText || '' }) }}"
    )
    ig_status = (
        "const raw = $input.first().json || {};\n"
        "const code = String(raw.status_code || '').toUpperCase();\n"
        "return [{ json: Object.assign({}, raw, { igReady: code === 'FINISHED' && !raw.error }) }];\n"
    )
    ig_mark = code_node(
        "IG mark",
        "story-ig-mark-" + channel,
        "let storyIg = false;\n"
        "try {\n"
        "  const row = $('IG story publish').first().json || {};\n"
        "  storyIg = !!(row.id && !row.error);\n"
        "} catch (e) {}\n"
        "return [{ json: { storyIg } }];\n",
        [3600, 0],
    )
    ig_mark["parameters"]["mode"] = "runOnceForAllItems"
    ig_mark["parameters"]["language"] = "javaScript"
    fb_mark = code_node(
        "FB mark",
        "story-fb-mark-" + channel,
        "let storyFb = false;\n"
        "try {\n"
        "  const row = $('FB story finish').first().json || {};\n"
        "  storyFb = (row.success === true || row.success === 'true') && !row.error;\n"
        "} catch (e) {}\n"
        "return [{ json: { storyFb } }];\n",
        [3600, 280],
    )
    fb_mark["parameters"]["mode"] = "runOnceForAllItems"
    fb_mark["parameters"]["language"] = "javaScript"
    check = code_node(
        "Story check",
        "story-check-" + channel,
        "const items = $input.all().map(item => item.json || {});\n"
        "const storyIg = items.some(row => row.storyIg === true);\n"
        "const storyFb = items.some(row => row.storyFb === true);\n"
        "if (!storyIg && !storyFb) throw new Error('Το story δεν ανέβηκε ούτε στο Instagram ούτε στο Facebook.');\n"
        "return [{ json: { storyIg, storyFb } }];\n",
        [4040, 140],
    )
    check["parameters"]["mode"] = "runOnceForAllItems"
    check["parameters"]["language"] = "javaScript"
    status_a = code_node("IG story status A", "story-ig-status-a-" + channel, ig_status, [1960, 0])
    status_b = code_node("IG story status B", "story-ig-status-b-" + channel, ig_status, [2620, 180])
    for node in (status_a, status_b):
        node["parameters"]["mode"] = "runOnceForAllItems"
        node["parameters"]["language"] = "javaScript"

    def story_code(name, node_id, js, position, notes=""):
        node = code_node(name, node_id, js, position, notes)
        node["parameters"]["mode"] = "runOnceForAllItems"
        node["parameters"]["language"] = "javaScript"
        return node

    def story_set(name, node_id, fields, position):
        return {
            "parameters": {
                "assignments": {
                    "assignments": [
                        {"id": node_id + "-" + field, "name": field, "value": value, "type": typ}
                        for field, value, typ in fields
                    ]
                },
                "includeOtherFields": False,
                "options": {},
            },
            "id": node_id,
            "name": name,
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": position,
        }

    rss_format = story_set(
        "RSS format",
        "rss-format-" + channel,
        [
            ("videoId", "={{ (String($json.link || '').match(/[?&]v=([^&]+)/) || String($json.link || '').match(/\\/shorts\\/([^/?]+)/) || [null,''])[1] || '' }}", "string"),
            ("title", "={{ $json.title || '' }}", "string"),
            ("link", "={{ $json.link || '' }}", "string"),
            ("requestId", "", "string"),
            ("clipStart", "auto", "string"),
            ("clipSeconds", "30", "number"),
            ("hookText", spec["rssHook"], "string"),
            ("ctaText", spec["cta"], "string"),
        ],
        [200, 320],
    )
    story_pack = story_set(
        "Story pack",
        "story-pack-" + channel,
        [
            ("videoId", "={{ $json.videoId || '' }}", "string"),
            ("title", "={{ $json.title || '' }}", "string"),
            ("requestId", "={{ $json.requestId || '' }}", "string"),
            ("clipStart", "={{ $json.clipStart || 'auto' }}", "string"),
            ("clipSeconds", "={{ Number($json.clipSeconds) || 30 }}", "number"),
            ("hookText", "={{ $json.hookText || '' }}", "string"),
            ("ctaText", "={{ $json.ctaText || '' }}", "string"),
        ],
        [140, 80],
    )
    rss_age = story_code(
        "RSS age",
        "rss-age-" + channel,
        "const item = $input.first().json || {};\n"
        "const published = Date.parse(String(item.isoDate || item.pubDate || ''));\n"
        "const fresh = Number.isFinite(published) && (Date.now() - published) < 48 * 60 * 60 * 1000;\n"
        "return [{ json: Object.assign({}, item, { fresh }) }];\n",
        [-280, 320],
    )
    long_check = story_code(
        "Long check",
        "rss-long-" + channel,
        "const pack = $('RSS format').first().json || {};\n"
        "const title = String(pack.title || '').toLowerCase();\n"
        "const link = String(pack.link || '');\n"
        "let dur = null;\n"
        "try {\n"
        "  const info = $('Video info').first().json || {};\n"
        "  dur = Number(info.durationSeconds || info.duration);\n"
        "} catch (e) {}\n"
        "const isShort = title.includes('#shorts') || link.includes('/shorts/') || (Number.isFinite(dur) && dur > 0 && dur <= 60);\n"
        "return [{ json: Object.assign({}, pack, { isShort }) }];\n",
        [680, 320],
    )
    dedup = story_code(
        "RSS dedup",
        "rss-dedup-" + channel,
        dedup_js("story"),
        [1160, 320],
        "Skip RSS if this videoId already storied.",
    )
    remember = story_code(
        "Remember story",
        "remember-story-" + channel,
        remember_js("story", "Story pack"),
        [4280, 140],
    )
    nodes = [
        webhook_node(spec, cred),
        normalize,
        {
            "id": "rss-" + channel,
            "name": "RSS " + channel,
            "type": "n8n-nodes-base.rssFeedReadTrigger",
            "typeVersion": 1,
            "position": [-520, 320],
            "parameters": {
                "pollTimes": {"item": [{"mode": "everyX", "value": 15, "unit": "minutes"}]},
                "feedUrl": "https://www.youtube.com/feeds/videos.xml?channel_id=" + spec["feed"],
            },
        },
        rss_age,
        if_node("If fresh", "rss-fresh-" + channel, "={{ $json.fresh === true }}", [-40, 320]),
        rss_format,
        video_info_node(channel, "RSS format", [440, 320]),
        long_check,
        if_node("Only long videos", "rss-only-long-" + channel, "={{ $json.isShort !== true }}", [920, 320]),
        dedup,
        if_node("If duplicate", "rss-dup-" + channel, "={{ $json.skipped === 'duplicate' }}", [1400, 320]),
        story_pack,
        {
            "id": "story-make-" + channel,
            "name": "Make story clip",
            "notes": "Κόβει κάθετο απόσπασμα 5–60s. Το πλήρες αρχείο δεν ανεβαίνει.",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 4000,
            "position": [280, 0],
            "parameters": {
                "method": "POST",
                "url": "http://n8n-reels:8080/short",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": clip_body,
                "options": {"timeout": 600000},
            },
        },
        if_node(
            "Clip ready",
            "story-clip-ready-" + channel,
            "={{ $json.ok === true && String($json.path || '').indexOf('/ytshort-') >= 0 && String($json.path || '').endsWith('.mp4') && String($json.path || '').indexOf('.src') < 0 }}",
            [520, 0],
        ),
        _story_throw("Story uncut", "story-uncut-" + channel, "Το απόσπασμα δεν κόπηκε.", [520, 200]),
        {
            "id": "story-read-" + channel,
            "name": "Read story file",
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1.1,
            "position": [760, 0],
            "parameters": {
                "operation": "read",
                "fileSelector": "=/work/ytshort-{{ $('Story pack').item.json.videoId }}.mp4",
                "options": {
                    "fileName": "=ytshort-{{ $('Story pack').item.json.videoId }}.mp4",
                    "mimeType": "video/mp4",
                },
            },
        },
        {
            "id": "story-r2-" + channel,
            "name": "Upload story",
            "type": "n8n-nodes-base.s3",
            "typeVersion": 1,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 4000,
            "position": [1000, 0],
            "parameters": {
                "operation": "upload",
                "bucketName": "mrbonzo-reels",
                "fileName": "={{ 'stories/' + $('Story pack').item.json.videoId + '.mp4' }}",
                "additionalFields": {},
            },
            "credentials": {"s3": STORY_S3},
        },
        if_node("Story uploaded", "story-uploaded-" + channel, "={{ !$json.error }}", [1240, 0]),
        _story_throw("Story missing", "story-missing-" + channel, "Το απόσπασμα δεν ανέβηκε.", [1240, 200]),
        _story_graph(
            "IG story create",
            "story-ig-create-" + channel,
            "/" + STORY_IG + "/media",
            [("media_type", "STORIES"), ("video_url", url)],
            [1480, 0],
        ),
        if_node("IG story created", "story-ig-created-" + channel, "={{ !!$json.id && !$json.error }}", [1720, 0]),
        _story_wait("Wait IG story A", "story-ig-wait-a-" + channel, 20, [1720, 180]),
        _story_graph(
            "IG story poll A",
            "story-ig-poll-a-" + channel,
            "=/{{ $('IG story create').first().json.id }}",
            [("fields", "status_code")],
            [1960, -160],
            method="GET",
        ),
        status_a,
        if_node("IG story ready A", "story-ig-ready-a-" + channel, "={{ $json.igReady === true }}", [2200, 0]),
        _story_wait("Wait IG story B", "story-ig-wait-b-" + channel, 25, [2200, 180]),
        _story_graph(
            "IG story poll B",
            "story-ig-poll-b-" + channel,
            "=/{{ $('IG story create').first().json.id }}",
            [("fields", "status_code")],
            [2440, 180],
            method="GET",
        ),
        status_b,
        if_node("IG story ready B", "story-ig-ready-b-" + channel, "={{ $json.igReady === true }}", [2860, 180]),
        _story_graph(
            "IG story publish",
            "story-ig-publish-" + channel,
            "/" + STORY_IG + "/media_publish",
            [("creation_id", "={{ $('IG story create').first().json.id }}")],
            [3100, 0],
        ),
        if_node("IG published", "story-ig-published-" + channel, "={{ !!$json.id && !$json.error }}", [3340, 0]),
        ig_mark,
        _story_graph(
            "FB story start",
            "story-fb-start-" + channel,
            "/me/video_stories",
            [("upload_phase", "start")],
            [1480, 280],
        ),
        if_node(
            "FB story started",
            "story-fb-started-" + channel,
            "={{ !!$json.video_id && !!$json.upload_url && !$json.error }}",
            [1720, 280],
        ),
        {
            "id": "story-fb-upload-" + channel,
            "name": "FB story upload",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "onError": "continueRegularOutput",
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 4000,
            "position": [1960, 280],
            "parameters": {
                "method": "POST",
                "url": "={{ $json.upload_url }}",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "facebookGraphApi",
                "sendHeaders": True,
                "headerParameters": {"parameters": [{"name": "file_url", "value": url}]},
                "options": {"timeout": 120000},
            },
            "credentials": {"facebookGraphApi": STORY_FB},
        },
        if_node(
            "FB story uploaded",
            "story-fb-uploaded-" + channel,
            "={{ !$json.error && ($json.success === true || $json.success === 'true') }}",
            [2200, 280],
        ),
        _story_graph(
            "FB story finish",
            "story-fb-finish-" + channel,
            "/me/video_stories",
            [("upload_phase", "finish"), ("video_id", "={{ $('FB story start').first().json.video_id }}")],
            [2440, 280],
        ),
        if_node(
            "FB story finished",
            "story-fb-finished-" + channel,
            "={{ ($json.success === true || $json.success === 'true') && !$json.error }}",
            [2680, 280],
        ),
        fb_mark,
        {
            "id": "story-both-" + channel,
            "name": "Story both",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3.2,
            "position": [3840, 140],
            "parameters": {"mode": "append", "numberInputs": 2},
        },
        check,
        remember,
    ]
    # Webhook from webhook_node sits at its own position; keep the graph readable.
    nodes[0]["position"] = [-280, 0]
    links = [
        (spec["webhook"], [[edge("Manual normalize")]]),
        ("Manual normalize", [[edge("Story pack")]]),
        ("RSS " + channel, [[edge("RSS age")]]),
        ("RSS age", [[edge("If fresh")]]),
        ("If fresh", [[edge("RSS format")], []]),
        ("RSS format", [[edge("Video info")]]),
        ("Video info", [[edge("Long check")]]),
        ("Long check", [[edge("Only long videos")]]),
        ("Only long videos", [[edge("RSS dedup")], []]),
        ("RSS dedup", [[edge("If duplicate")]]),
        ("If duplicate", [[], [edge("Story pack")]]),
        ("Story pack", [[edge("Make story clip")]]),
        ("Make story clip", [[edge("Clip ready")]]),
        ("Clip ready", [[edge("Read story file")], [edge("Story uncut")]]),
        ("Read story file", [[edge("Upload story")]]),
        ("Upload story", [[edge("Story uploaded")]]),
        ("Story uploaded", [[edge("IG story create"), edge("FB story start")], [edge("Story missing")]]),
        ("IG story create", [[edge("IG story created")]]),
        ("IG story created", [[edge("Wait IG story A")], [edge("IG mark")]]),
        ("Wait IG story A", [[edge("IG story poll A")]]),
        ("IG story poll A", [[edge("IG story status A")]]),
        ("IG story status A", [[edge("IG story ready A")]]),
        ("IG story ready A", [[edge("IG story publish")], [edge("Wait IG story B")]]),
        ("Wait IG story B", [[edge("IG story poll B")]]),
        ("IG story poll B", [[edge("IG story status B")]]),
        ("IG story status B", [[edge("IG story ready B")]]),
        ("IG story ready B", [[edge("IG story publish")], [edge("IG mark")]]),
        ("IG story publish", [[edge("IG published")]]),
        ("IG published", [[edge("IG mark")], [edge("IG mark")]]),
        ("IG mark", [[edge("Story both", 0)]]),
        ("FB story start", [[edge("FB story started")]]),
        ("FB story started", [[edge("FB story upload")], [edge("FB mark")]]),
        ("FB story upload", [[edge("FB story uploaded")]]),
        ("FB story uploaded", [[edge("FB story finish")], [edge("FB mark")]]),
        ("FB story finish", [[edge("FB story finished")]]),
        ("FB story finished", [[edge("FB mark")], [edge("FB mark")]]),
        ("FB mark", [[edge("Story both", 1)]]),
        ("Story both", [[edge("Story check")]]),
        ("Story check", [[edge("Remember story")]]),
    ]
    wf["nodes"] = nodes
    wf["connections"] = {}
    for src, groups in links:
        set_main(wf, src, groups)
    settings = wf.setdefault("settings", {})
    settings["executionTimeout"] = 1800
    settings["timezone"] = "Europe/Athens"
    return True


def patch_workflow(wf, cred=None):
    """Mutate wf. Returns True when this workflow is one of the panel workflows and was patched."""
    spec = SPECS.get(wf.get("name") or "")
    if not spec:
        return False
    settings = wf.setdefault("settings", {})
    settings.setdefault("timezone", "Europe/Athens")
    settings.setdefault("errorWorkflow", "a1111111-e110-4e57-a000-00000000err1")
    if spec["kind"] == "post":
        ok = patch_post(wf, spec, cred)
    elif spec["kind"] == "story":
        ok = patch_story(wf, spec, cred)
    else:
        ok = patch_short(wf, spec, cred)
    apply_retries(wf)
    return ok


def missing_sensitive_credentials(wf):
    bad = []
    for node in wf.get("nodes") or []:
        if node.get("type") in SENSITIVE and not node.get("credentials"):
            bad.append(node.get("name") or node.get("type"))
    return bad


def targets(wf):
    found = []
    for src, conn in (wf.get("connections") or {}).items():
        for group in conn.get("main") or []:
            for item in group or []:
                found.append((src, item.get("node")))
    names = {node.get("name") for node in wf.get("nodes") or []}
    return [pair for pair in found if pair[1] not in names]
