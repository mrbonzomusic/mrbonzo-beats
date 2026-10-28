const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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
  const apiRoot = String(env.PLUNK_API_URL || "").replace(/\/$/, "");
  const secret = env.PLUNK_SECRET_KEY || "";

  if (!apiRoot || !secret) {
    return json({ ok: false, error: "not_ready" }, 503);
  }

  const payload = JSON.stringify({
    email,
    subscribed: true,
    data: { locale: lang, source: "website" },
  });

  const headers = {
    Authorization: "Bearer " + secret,
    "Content-Type": "application/json",
  };

  const paths = ["/v1/contacts", "/contacts"];
  for (const path of paths) {
    try {
      const res = await fetch(apiRoot + path, {
        method: "POST",
        headers,
        body: payload,
      });
      if (res.ok) return json({ ok: true }, 200);
      if (res.status !== 404) return json({ ok: false, error: "upstream" }, 502);
    } catch {
      /* try next path */
    }
  }

  return json({ ok: false, error: "upstream" }, 502);
}
