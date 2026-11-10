"""Official site and BaseBox weekly Facebook: panel settings, n8n schedule/texts, manual webhook."""
import json

from workflow_patch import CRED_NAME, edge, set_main, upsert, webhook_node

ERROR_ID = "a1111111-e110-4e57-a000-00000000err1"

OFFICIAL_COPY = [
    "Επίσημο site του Mr. Bonzo. Beats, κυκλοφορίες και το στούντιο.",
    "Άκου τα beats και δες τις κυκλοφορίες.",
    "Boom bap, trap και οι κυκλοφορίες, σε ένα site.",
    "Παραγωγή, beats και το Purple Sound Studio.",
    "Οι κυκλοφορίες και τα beats του Mr. Bonzo.",
    "Από το beat μέχρι την κυκλοφορία, στο επίσημο site.",
]
BASEBOX_COPY = [
    "Ο κατάλογος, οργανωμένος. Έργα, συντελεστές, ποσοστά και φόρμες ΟΣΔ σε ένα σημείο.",
    "Έργα, συντελεστές και μερίδια, για ανεξάρτητους καλλιτέχνες και μικρά labels.",
    "Οι φόρμες ΟΣΔ γεμίζουν από τον κατάλογο, χωρίς να ξαναγράφεις τα ίδια στοιχεία.",
    "Split sheets, ποσοστά και ρόλοι, έτοιμα για την επόμενη κυκλοφορία.",
    "Από το τραγούδι μέχρι το συμφωνητικό, σε ένα workspace.",
    "Φτιαγμένο από μουσικό, για ανεξάρτητους καλλιτέχνες και μικρά labels.",
]

DAYS = [
    {"id": 1, "label": "Δευτέρα"},
    {"id": 2, "label": "Τρίτη"},
    {"id": 3, "label": "Τετάρτη"},
    {"id": 4, "label": "Πέμπτη"},
    {"id": 5, "label": "Παρασκευή"},
    {"id": 6, "label": "Σάββατο"},
    {"id": 0, "label": "Κυριακή"},
]

DEFAULTS = {
    "official": {
        "id": "official",
        "name": "Official site weekly Facebook",
        "label": "Official site",
        "path": "weekly-official",
        "webhook": "Manual weekly official",
        "file": "official-site-weekly-facebook.json",
        "weekday": 4,
        "hour": 10,
        "minute": 0,
        "link": "https://mrbonzo-beats.pages.dev/",
        "image": "https://mrbonzo-beats.pages.dev/og-image-v2.jpg",
        "texts": OFFICIAL_COPY,
        "pages": [
            {
                "id": "mrbonzo",
                "label": "Mr. Bonzo",
                "rule": "twice_month",
                "texts": OFFICIAL_COPY,
            },
            {
                "id": "studio",
                "label": "Purple Sound Studio",
                "rule": "day_15_21",
                "texts": OFFICIAL_COPY,
            },
        ],
    },
    "basebox": {
        "id": "basebox",
        "name": "BaseBox weekly Facebook",
        "label": "BaseBox-DB",
        "path": "weekly-basebox",
        "webhook": "Manual weekly BaseBox",
        "file": "basebox-weekly-facebook.json",
        "weekday": 2,
        "hour": 10,
        "minute": 0,
        "link": "https://basebox-db.com/",
        "image": "https://basebox-db.com/branding/social/og-landing.png?v=21",
        "texts": BASEBOX_COPY,
        "pages": [
            {
                "id": "basebox",
                "label": "BaseBox",
                "rule": "always",
                "texts": BASEBOX_COPY,
            },
            {
                "id": "mrbonzo",
                "label": "Mr. Bonzo",
                "rule": "day_1_7",
                "texts": BASEBOX_COPY,
            },
            {
                "id": "studio",
                "label": "Purple Sound Studio",
                "rule": "day_15_21",
                "texts": BASEBOX_COPY,
            },
        ],
    },
}


def clone_default(cid):
    return json.loads(json.dumps(DEFAULTS[cid], ensure_ascii=False))


def normalize_campaign(cid, data):
    base = clone_default(cid)
    if not isinstance(data, dict):
        return base
    weekday = data.get("weekday", base["weekday"])
    try:
        weekday = int(weekday)
    except (TypeError, ValueError):
        weekday = base["weekday"]
    if weekday not in (0, 1, 2, 3, 4, 5, 6):
        weekday = base["weekday"]
    try:
        hour = int(data.get("hour", base["hour"]))
    except (TypeError, ValueError):
        hour = base["hour"]
    hour = max(0, min(23, hour))
    try:
        minute = int(data.get("minute", base["minute"]))
    except (TypeError, ValueError):
        minute = base["minute"]
    minute = max(0, min(59, minute))
    base["weekday"] = weekday
    base["hour"] = hour
    base["minute"] = minute
    base["link"] = str(data.get("link") or base["link"]).strip() or base["link"]
    base["image"] = str(data.get("image") or base["image"]).strip() or base["image"]
    incoming = {item.get("id"): item for item in (data.get("pages") or []) if isinstance(item, dict)}
    pages = []
    for page in base["pages"]:
        hit = incoming.get(page["id"]) or {}
        texts = hit.get("texts", page["texts"])
        if isinstance(texts, str):
            texts = [line.strip() for line in texts.splitlines() if line.strip()]
        elif isinstance(texts, list):
            texts = [str(line).strip() for line in texts if str(line).strip()]
        else:
            texts = page["texts"]
        if not texts:
            texts = page["texts"]
        rule = hit.get("rule") or page["rule"]
        if rule not in ("always", "day_1_7", "day_15_21", "twice_month"):
            rule = page["rule"]
        if cid == "official" and page["id"] == "mrbonzo" and rule == "always":
            rule = "twice_month"
        pages.append({
            "id": page["id"],
            "label": page["label"],
            "rule": rule,
            "texts": texts[:24],
        })
    if cid in ("official", "basebox"):
        raw_texts = data.get("texts")
        if isinstance(raw_texts, str):
            chosen = [line.strip() for line in raw_texts.splitlines() if line.strip()]
        elif isinstance(raw_texts, list):
            chosen = [str(line).strip() for line in raw_texts if str(line).strip()]
        else:
            chosen = []
        if not chosen:
            chosen = list(base.get("texts") or [])
        chosen = chosen[:24]
        for page in pages:
            page["texts"] = list(chosen)
        base["texts"] = chosen
    base["pages"] = pages
    return base


def pick_posts_code(cfg):
    pools = {page["id"]: page["texts"] for page in cfg["pages"]}
    rules = {page["id"]: page["rule"] for page in cfg["pages"]}
    return (
        "const now = $now.setZone('Europe/Athens');\n"
        "const week = now.weekNumber;\n"
        "const day = now.day;\n"
        "const month = now.month;\n"
        "const raw = $input.first().json || {};\n"
        "const input = (raw.body && typeof raw.body === 'object') ? Object.assign({}, raw, raw.body) : raw;\n"
        "const testPage = String(input.testPage || '');\n"
        "const pagesIn = Array.isArray(input.pages) ? input.pages.map(String).filter(Boolean) : [];\n"
        "const luxonDay = now.weekday;\n"
        "const panelDay = luxonDay === 7 ? 0 : luxonDay;\n"
        "if (!pagesIn.length && !testPage && panelDay !== %d) return [];\n"
        "const customCaption = String(input.caption || '');\n"
        "const image = String(input.image || %s);\n"
        "const link = String(input.link || %s);\n"
        "const pools = %s;\n"
        "const rules = %s;\n"
        "const line = (text) => {\n"
        "  const t = String(text || '').trim();\n"
        "  if (!t) return link;\n"
        "  if (/https?:\\/\\//i.test(t)) return t;\n"
        "  return t + String.fromCharCode(10) + link;\n"
        "};\n"
        "const want = (page) => {\n"
        "  if (pagesIn.length) return pagesIn.includes(page);\n"
        "  if (testPage) return testPage === page;\n"
        "  const rule = rules[page] || 'always';\n"
        "  if (rule === 'day_1_7') return day <= 7;\n"
        "  if (rule === 'day_15_21') return day >= 15 && day <= 21;\n"
        "  if (rule === 'twice_month') return day <= 7 || (day >= 15 && day <= 21);\n"
        "  return true;\n"
        "};\n"
        "const captionFor = (page) => {\n"
        "  if (customCaption) return line(customCaption);\n"
        "  const pool = pools[page] || [''];\n"
        "  const idx = (rules[page] === 'always' || rules[page] === 'twice_month') ? week : Math.max(0, month - 1);\n"
        "  return line(pool[idx %% pool.length] || pool[0] || '');\n"
        "};\n"
        "const posts = [];\n"
        "for (const page of Object.keys(pools)) {\n"
        "  if (!want(page)) continue;\n"
        "  posts.push({ json: { page, caption: captionFor(page), image, link } });\n"
        "}\n"
        "return posts;\n"
    ) % (
        int(cfg["weekday"]),
        json.dumps(cfg["image"], ensure_ascii=False),
        json.dumps(cfg["link"], ensure_ascii=False),
        json.dumps(pools, ensure_ascii=False),
        json.dumps(rules, ensure_ascii=False),
    )


def weekly_normalize(spec):
    rows = [
        ("testPage", "={{ ($json.body && $json.body.testPage) || '' }}", "string"),
        ("caption", "={{ ($json.body && $json.body.caption) || '' }}", "string"),
        ("image", "={{ ($json.body && $json.body.image) || '' }}", "string"),
        ("link", "={{ ($json.body && $json.body.link) || '' }}", "string"),
        ("pages", "={{ ($json.body && $json.body.pages) || [] }}", "array"),
    ]
    return {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "wkn-%s" % name, "name": name, "value": value, "type": typ}
                    for name, value, typ in rows
                ]
            },
            "includeOtherFields": False,
            "options": {},
        },
        "id": "wkn-" + spec["path"],
        "name": "Weekly normalize",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-40, 460],
    }


PROMO_URL = "https://pub-1cb7f846eb8e4ab998a9cf2e22cc3c75.r2.dev/promo/official-site-story.mp4"
PROMO_FILE = "/home/node/.n8n/promo/official-site-story.mp4"
IG_STORY = "17841404419062410"
FB_MR = {"id": "HzmFdeNPMKO2sQtk", "name": "Facebook Mr Bonzo"}
FB_STUDIO = {"id": "2j5nLm4cM61OnjnE", "name": "Facebook Purple Sound"}
S3_CRED = {"id": "7uiqHIsogZqpfxT8", "name": "S3 account"}


def _code(name, node_id, js, position):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": js},
    }


def _if_true(name, node_id, left, position):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [{
                    "id": node_id + "-c",
                    "leftValue": left,
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
    }


def _graph(name, node_id, cred, path, params, position, method="POST"):
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
        "credentials": {"facebookGraphApi": cred},
    }


def _wait(name, node_id, seconds, position):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "webhookId": node_id,
        "position": position,
        "parameters": {"amount": seconds},
    }


def _fb_story_chain(page, cred, y):
    start = "FB story start " + page
    upload = "FB story upload " + page
    finish = "FB story finish " + page
    return [
        _if_true(
            "Story page " + page,
            "story-page-" + page,
            "={{ ($('Story once').first().json.pages || []).includes('%s') }}" % page,
            [1960, y],
        ),
        _graph(start, "story-start-" + page, cred, "/me/video_stories", [("upload_phase", "start")], [2180, y]),
        _if_true(
            "FB story started " + page,
            "story-started-" + page,
            "={{ !!$json.video_id && !!$json.upload_url && !$json.error }}",
            [2400, y],
        ),
        {
            "id": "story-upload-" + page,
            "name": upload,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "onError": "continueRegularOutput",
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 4000,
            "position": [2620, y],
            "parameters": {
                "method": "POST",
                "url": "={{ $json.upload_url }}",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "facebookGraphApi",
                "sendHeaders": True,
                "headerParameters": {"parameters": [{"name": "file_url", "value": PROMO_URL}]},
                "options": {"timeout": 120000},
            },
            "credentials": {"facebookGraphApi": cred},
        },
        _if_true(
            "FB story uploaded " + page,
            "story-uploaded-" + page,
            "={{ !$json.error && ($json.success === true || $json.success === 'true') }}",
            [2840, y],
        ),
        _graph(
            finish,
            "story-finish-" + page,
            cred,
            "/me/video_stories",
            [("upload_phase", "finish"), ("video_id", "={{ $('%s').first().json.video_id }}" % start)],
            [3060, y],
        ),
    ], [
        ("Story page " + page, [[edge(start)], []]),
        (start, [[edge("FB story started " + page)]]),
        ("FB story started " + page, [[edge(upload)], []]),
        (upload, [[edge("FB story uploaded " + page)]]),
        ("FB story uploaded " + page, [[edge(finish)], []]),
    ]


def ensure_official_stories(wf):
    """Keep the promo story branch on the official-site workflow. Photo posts stay independent."""
    ig_status = (
        "const raw = $input.first().json || {};\n"
        "const code = String(raw.status_code || '').toUpperCase();\n"
        "return [{ json: Object.assign({}, raw, { igReady: code === 'FINISHED' && !raw.error }) }];\n"
    )
    nodes = [
        _code(
            "Story once",
            "story-once",
            "const pages = [];\n"
            "for (const item of $input.all()) {\n"
            "  const page = String((item.json || {}).page || '');\n"
            "  if (page && pages.indexOf(page) === -1) pages.push(page);\n"
            "}\n"
            "if (!pages.length) return [];\n"
            "return [{ json: { pages } }];\n",
            [860, 700],
        ),
        {
            "id": "story-read",
            "name": "Read promo",
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1.1,
            "onError": "continueRegularOutput",
            "position": [1080, 700],
            "parameters": {
                "operation": "read",
                "fileSelector": PROMO_FILE,
                "options": {"fileName": "official-site-story.mp4", "mimeType": "video/mp4"},
            },
        },
        {
            "id": "story-r2",
            "name": "Upload promo",
            "type": "n8n-nodes-base.s3",
            "typeVersion": 1,
            "onError": "continueRegularOutput",
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 4000,
            "position": [1300, 700],
            "parameters": {
                "operation": "upload",
                "bucketName": "mrbonzo-reels",
                "fileName": "promo/official-site-story.mp4",
                "additionalFields": {},
            },
            "credentials": {"s3": S3_CRED},
        },
        _if_true("Promo uploaded", "story-uploaded", "={{ !$json.error }}", [1520, 700]),
        _graph(
            "IG story create",
            "story-ig-create",
            FB_MR,
            "/" + IG_STORY + "/media",
            [("media_type", "STORIES"), ("video_url", PROMO_URL)],
            [1740, 620],
        ),
        _if_true("IG story created", "story-ig-created", "={{ !!$json.id && !$json.error }}", [1960, 620]),
        _wait("Wait IG story A", "story-ig-wait-a", 20, [2180, 620]),
        _graph(
            "IG story poll A",
            "story-ig-poll-a",
            FB_MR,
            "=/{{ $('IG story create').first().json.id }}",
            [("fields", "status_code")],
            [2400, 620],
            method="GET",
        ),
        _code("IG story status A", "story-ig-status-a", ig_status, [2620, 620]),
        _if_true("IG story ready A", "story-ig-ready-a", "={{ $json.igReady === true }}", [2840, 620]),
        _wait("Wait IG story B", "story-ig-wait-b", 25, [2840, 800]),
        _graph(
            "IG story poll B",
            "story-ig-poll-b",
            FB_MR,
            "=/{{ $('IG story create').first().json.id }}",
            [("fields", "status_code")],
            [3060, 800],
            method="GET",
        ),
        _code("IG story status B", "story-ig-status-b", ig_status, [3280, 800]),
        _if_true("IG story ready B", "story-ig-ready-b", "={{ $json.igReady === true }}", [3500, 800]),
        _graph(
            "IG story publish",
            "story-ig-publish",
            FB_MR,
            "/" + IG_STORY + "/media_publish",
            [("creation_id", "={{ $('IG story create').first().json.id }}")],
            [3720, 620],
        ),
    ]
    links = [
        ("Story once", [[edge("Read promo")]]),
        ("Read promo", [[edge("Upload promo")]]),
        ("Upload promo", [[edge("Promo uploaded")]]),
        ("Promo uploaded", [[edge("IG story create"), edge("Story page mrbonzo"), edge("Story page studio")], []]),
        ("IG story create", [[edge("IG story created")]]),
        ("IG story created", [[edge("Wait IG story A")], []]),
        ("Wait IG story A", [[edge("IG story poll A")]]),
        ("IG story poll A", [[edge("IG story status A")]]),
        ("IG story status A", [[edge("IG story ready A")]]),
        ("IG story ready A", [[edge("IG story publish")], [edge("Wait IG story B")]]),
        ("Wait IG story B", [[edge("IG story poll B")]]),
        ("IG story poll B", [[edge("IG story status B")]]),
        ("IG story status B", [[edge("IG story ready B")]]),
        ("IG story ready B", [[edge("IG story publish")], []]),
    ]
    for page, cred, y in (("mrbonzo", FB_MR, 900), ("studio", FB_STUDIO, 1140)):
        extra, extra_links = _fb_story_chain(page, cred, y)
        nodes.extend(extra)
        links.extend(extra_links)
    for node in nodes:
        upsert(wf, node)
    for src, groups in links:
        set_main(wf, src, groups)
    set_main(wf, "Pick posts", [[
        edge("Page is Mr Bonzo"),
        edge("Page is Purple Sound"),
        edge("Story once"),
    ]])
    for node in wf.get("nodes") or []:
        if node.get("name") == "Note":
            node.setdefault("parameters", {})["content"] = (
                "## Official site weekly Facebook\n\n"
                "Κάθε Πέμπτη 10:00, ώρα Αθήνας.\n\n"
                "- Mr. Bonzo: δύο Πέμπτες τον μήνα, μέρες 1–7 και 15–21\n"
                "- Purple Sound Studio: Πέμπτη στις 15–21\n"
                "- Story στο Instagram μία φορά, και video story στη σελίδα που ποστάρει\n\n"
                "Προγραμματισμένο τρέξιμο που δεν είναι Πέμπτη δεν δημοσιεύει.\n\n"
                "Εικόνα: og-image-v2.jpg\n"
                "Σύνδεσμος: https://mrbonzo-beats.pages.dev/\n"
                "Story: official-site-story.mp4\n"
            )
    return True


def patch_weekly_workflow(wf, cfg, cred=None):
    spec = {
        "path": cfg["path"],
        "webhook": cfg["webhook"],
        "kind": "post",
        "channel": cfg["id"],
    }
    upsert(wf, webhook_node(spec, cred))
    upsert(wf, weekly_normalize(spec))
    pick = None
    schedule = None
    for node in wf.get("nodes") or []:
        if node.get("name") == "Pick posts":
            pick = node
        if node.get("type") == "n8n-nodes-base.scheduleTrigger":
            schedule = node
    if pick:
        pick.setdefault("parameters", {})["jsCode"] = pick_posts_code(cfg)
        pick["parameters"]["mode"] = "runOnceForAllItems"
        pick["parameters"]["language"] = "javaScript"
    if schedule:
        schedule.setdefault("parameters", {})["rule"] = {
            "interval": [{
                "field": "weeks",
                "weeksInterval": 1,
                "triggerAtDay": [cfg["weekday"]],
                "triggerAtHour": cfg["hour"],
                "triggerAtMinute": cfg["minute"],
            }]
        }
    settings = wf.setdefault("settings", {})
    settings["timezone"] = "Europe/Athens"
    settings["errorWorkflow"] = ERROR_ID
    set_main(wf, spec["webhook"], [[edge("Weekly normalize")]])
    set_main(wf, "Weekly normalize", [[edge("Pick posts")]])
    if schedule:
        set_main(wf, schedule.get("name"), [[edge("Pick posts")]])
    if cfg.get("id") == "official":
        ensure_official_stories(wf)
    return True
