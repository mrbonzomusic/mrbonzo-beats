"""Platform copy for YouTube, Facebook, Instagram, TikTok. Keep in sync with Format nodes."""
import re


def watch_url(video_id="", link=""):
    vid = (video_id or "").strip()
    if not vid and link:
        text = link
        for prefix, splitter in (("v=", "&"), ("/shorts/", "?"), ("youtu.be/", "?")):
            if prefix in text:
                vid = text.split(prefix, 1)[1].split(splitter)[0].split("/")[0]
                break
    if vid:
        return "https://www.youtube.com/watch?v=" + vid
    return (link or "").strip()


def caption_fb(channel, title, link=""):
    name = (title or "New release").strip()[:120]
    if channel == "mrbonzobeats":
        return "\n".join([
            "New type beat: " + name,
            "",
            "Stream the full instrumental on YouTube. Like and subscribe for more beats.",
            "",
            "#typebeat #instrumental #mrbonzo",
        ])
    return "\n".join([
        "New music: " + name,
        "",
        "Stream the full track on YouTube. Like and subscribe for more.",
        "",
        "#mrbonzo #hiphop #newmusic",
    ])


def caption_fb_archive(channel, title, link=""):
    name = (title or "Archive").strip()[:120]
    url = watch_url("", link) or (link or "").strip()
    if channel == "mrbonzobeats":
        return "\n".join([
            "Earlier beat: " + name,
            "",
            "From the archive. Full beat on YouTube.",
            "",
            url,
            "",
            "#typebeat #instrumental #mrbonzo",
        ])
    return "\n".join([
        "Από το αρχείο: " + name,
        "",
        "Ολόκληρο το τραγούδι στο YouTube.",
        "",
        url,
        "",
        "#mrbonzo #hiphop",
    ])


def caption_social(channel, title):
    name = (title or "New release").strip()[:80]
    if channel == "mrbonzobeats":
        return "\n".join([
            "New type beat: " + name,
            "Full beat — link in bio",
            "",
            "#typebeat #beatmaker #instrumental #mrbonzo #greece",
        ])
    return "\n".join([
        "New music: " + name,
        "Full track — link in bio",
        "",
        "#mrbonzo #hiphop #newmusic #greece #purplesound",
    ])


def caption_social_archive(channel, title):
    name = (title or "Archive").strip()[:80]
    if channel == "mrbonzobeats":
        return "\n".join([
            "Earlier beat: " + name,
            "Link in bio",
            "",
            "#typebeat #beatmaker #instrumental #mrbonzo #greece",
        ])
    return "\n".join([
        "Από το αρχείο: " + name,
        "Link in bio",
        "",
        "#mrbonzo #hiphop #greece #purplesound",
    ])


def beat_short_name(title):
    text = (title or "").replace("#Shorts", "").replace("#shorts", "").strip()
    quoted = re.search(r'["“](.+?)["”]', text)
    if quoted and quoted.group(1).strip():
        name = quoted.group(1).strip()
    else:
        name = re.sub(r"(?i)\s*\|.*$", "", text)
        name = re.sub(r"(?i)^\[free\]\s*", "", name)
        name = re.sub(r"(?i)\b(old school|boom bap|instrumental hip hop|type beat|free)\b", " ", name)
        name = re.sub(r"\[[^\]]*\]", " ", name)
        name = re.sub(r"\s+", " ", name).strip(" -–—|")
    name = re.sub(r"(?i)\s*type beat\s*$", "", name).strip(" -–—|")
    return ((name or "Beat")[:40].rstrip(" -–—|") or "Beat") + " Type Beat"


def short_title_seo(channel, title):
    suffix = " #Shorts"
    keep = 70 - len(suffix)
    if channel == "mrbonzobeats":
        base = beat_short_name(title)
    else:
        base = (title or "New release").replace("#Shorts", "").replace("#shorts", "").strip()
    if len(base) > keep:
        base = base[:keep].rstrip(" -–—|,")
    return (base or "New release") + suffix


def short_description_seo(channel, link, title="", video_id="", archive=False):
    url = watch_url(video_id, link)
    name = (title or "New release").strip()[:80]
    if archive:
        tags = (
            "#Shorts #typebeat #mrbonzo #instrumental"
            if channel == "mrbonzobeats"
            else "#Shorts #mrbonzo #hiphop"
        )
        return "%s\n\nWatch the full track: %s\n\n%s" % (name, url, tags)
    if channel == "mrbonzobeats":
        hook = "New type beat by Mr. Bonzo"
        tags = "#Shorts #typebeat #mrbonzo #instrumental"
    else:
        hook = "New music by Mr. Bonzo"
        tags = "#Shorts #mrbonzo #hiphop #newmusic"
    return "%s\n\nWatch the full track: %s\n\n%s" % (hook if not name else name, url, tags)


def n8n_fb_expr(channel):
    if channel == "mrbonzobeats":
        body = (
            "const t = String($json.title || 'New type beat').slice(0, 120); "
            "return ['New type beat: ' + t, '', "
            "'Stream the full instrumental on YouTube. Like and subscribe for more beats.', '', "
            "'#typebeat #instrumental #mrbonzo'].join('\\n');"
        )
    else:
        body = (
            "const t = String($json.title || 'New music').slice(0, 120); "
            "return ['New music: ' + t, '', "
            "'Stream the full track on YouTube. Like and subscribe for more.', '', "
            "'#mrbonzo #hiphop #newmusic'].join('\\n');"
        )
    return "={{ $json.messageFb || $json.message || (() => { %s })() }}" % body


def n8n_social_expr(channel):
    if channel == "mrbonzobeats":
        body = (
            "const t = String($json.title || 'New type beat').slice(0, 80); "
            "return ['New type beat: ' + t, 'Full beat — link in bio', '', "
            "'#typebeat #beatmaker #instrumental #mrbonzo #greece'].join('\\n');"
        )
    else:
        body = (
            "const t = String($json.title || 'New music').slice(0, 80); "
            "return ['New music: ' + t, 'Full track — link in bio', '', "
            "'#mrbonzo #hiphop #newmusic #greece #purplesound'].join('\\n');"
        )
    return "={{ $json.messageSocial || (() => { %s })() }}" % body


def n8n_short_title_expr(channel=""):
    beats = ""
    if channel == "mrbonzobeats":
        beats = (
            "const q = raw.match(/[\"“](.+?)[\"”]/); "
            "let name = q && q[1].trim() ? q[1].trim() : raw; "
            "if (!q) { "
            "name = name.replace(/\\s*\\|.*$/, ''); "
            "name = name.replace(/^\\[free\\]\\s*/i, ''); "
            "name = name.replace(/\\b(old school|boom bap|instrumental hip hop|type beat|free)\\b/ig, ' '); "
            "name = name.replace(/\\[[^\\]]*\\]/g, ' '); "
            "name = name.replace(/\\s+/g, ' ').replace(/^[\\s\\-–—|]+|[\\s\\-–—|]+$/g, ''); "
            "} "
            "name = name.replace(/\\s*type beat\\s*$/i, '').trim(); "
            "name = (name || 'Beat').slice(0, 40).replace(/[\\s\\-–—|]+$/, ''); "
            "t = (name || 'Beat') + ' Type Beat'; "
        )
    return (
        "={{ $json.shortTitle || (() => { "
        "const suffix = ' #Shorts'; "
        "const raw = String($json.title || 'New release').replace(/#Shorts/ig, '').trim(); "
        "let t = raw; "
        "%s"
        "const keep = 70 - suffix.length; "
        "if (t.length > keep) t = t.slice(0, keep).replace(/[\\s\\-–,|]+$/,''); "
        "return (t || 'New release') + suffix; })() }}"
    ) % beats


def n8n_short_desc_expr(channel):
    hook = "New type beat by Mr. Bonzo" if channel == "mrbonzobeats" else "New music by Mr. Bonzo"
    tags = "#Shorts #typebeat #mrbonzo #instrumental" if channel == "mrbonzobeats" else "#Shorts #mrbonzo #hiphop #newmusic"
    return (
        "={{ $json.shortDescription || (() => { "
        "const title = String($json.title || %s); "
        "const link = String($json.link || ''); "
        "const vid = (link.match(/[?&]v=([^&]+)/) || link.match(/\\/shorts\\/([^/?]+)/) || [null,''])[1]; "
        "const url = vid ? ('https://www.youtube.com/watch?v=' + vid) : link; "
        "return title + '\\n\\nWatch the full track: ' + url + '\\n\\n' + %s; })() }}"
    ) % (json_str(hook), json_str(tags))


def json_str(text):
    import json
    return json.dumps(text, ensure_ascii=False)
