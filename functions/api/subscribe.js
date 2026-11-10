const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NEWSLETTER_ENABLED = true;
const MAILERLITE_SUBSCRIBERS = "https://connect.mailerlite.com/api/subscribers";

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export function onRequestOptions() {
  return new Response(null, { status: 204 });
}

export async function onRequestPost({ request, env }) {
  if (!NEWSLETTER_ENABLED) {
    return json({ ok: false, error: "not_ready" }, 503);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "invalid" }, 400);
  }

  if (typeof body.company_url === "string" && body.company_url.trim()) {
    return json({ ok: true }, 200);
  }

  const email = String(body.email || "").trim().toLowerCase();
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return json({ ok: false, error: "email" }, 400);
  }

  const lang = body.lang === "el" ? "el" : "en";
  const token = env.MAILERLITE_API_TOKEN || "";
  const groupId = String(env.MAILERLITE_GROUP_ID || "").trim();

  if (!token || !groupId) {
    return json({ ok: false, error: "not_ready" }, 503);
  }

  const payload = {
    email,
    fields: { locale: lang, source: "website" },
    groups: [groupId],
    status: "active",
  };

  const headers = {
    Authorization: "Bearer " + token,
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  try {
    let res = await fetch(MAILERLITE_SUBSCRIBERS, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok && res.status === 422) {
      res = await fetch(MAILERLITE_SUBSCRIBERS, {
        method: "POST",
        headers,
        body: JSON.stringify({ email, groups: [groupId], status: "active" }),
      });
    }
    if (res.ok) return json({ ok: true }, 200);
    return json({ ok: false, error: "upstream" }, 502);
  } catch {
    return json({ ok: false, error: "upstream" }, 502);
  }
}
