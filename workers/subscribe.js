/** Cloudflare Worker: odběr novinek (Ecomail) + návrhy korektur (Resend). */

const CORS = {
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const RATE_LIMIT_PLACEHOLDER = "00000000000000000000000000000000";

const CORRECTION_KINDS = new Set(["factual", "typo", "other"]);

export default {
  async fetch(request, env) {
    const headers = corsHeaders(request, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers });
    }

    const path = new URL(request.url).pathname.replace(/\/+$/, "") || "/";
    if (path === "/corrections") {
      if (request.method === "GET") {
        return json({ ok: true, service: "corrections" }, 200, headers);
      }
      if (request.method !== "POST") {
        return new Response("Method not allowed", { status: 405, headers });
      }
      return handleCorrections(request, env, headers);
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers });
    }
    return handleSubscribe(request, env, headers);
  },
};

function corsHeaders(request, env) {
  const allowed = (env.ALLOWED_ORIGIN || "https://poslusnehlasim.cz")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const requestOrigin = request.headers.get("Origin") || "";
  const corsOrigin =
    requestOrigin && allowed.includes(requestOrigin) ? requestOrigin : allowed[0];
  return { ...CORS, "Access-Control-Allow-Origin": corsOrigin };
}

async function handleSubscribe(request, env, headers) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false }, 400, headers);
  }

  const email = String(body.email || "").trim();
  const hp = String(body.hp || body.website || "").trim();
  if (hp || !email || !email.includes("@")) {
    return json({ ok: false }, 400, headers);
  }
  const listId = subscribeListId(env);
  if (!env.ECOMAIL_API_KEY || !listId) {
    return json({ ok: false, error: "misconfigured" }, 500, headers);
  }

  if (body.notify_failed) {
    return json({ ok: false }, 400, headers);
  }

  const rate = await enforceRateLimits(request, env, email);
  if (!rate.ok) {
    return json(
      { ok: false, error: "rate_limited" },
      429,
      { ...headers, "Retry-After": String(rate.retryAfter) },
    );
  }

  const res = await fetch(
    `https://api2.ecomailapp.cz/lists/${listId}/subscribe`,
    {
      method: "POST",
      headers: {
        key: env.ECOMAIL_API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        subscriber_data: { email, source: "poslusnehlasim" },
        trigger_autoresponders: true,
        update_existing: true,
        resubscribe: true,
        skip_confirmation: false,
      }),
    },
  );

  if (!res.ok) {
    await notifyAdminSubscribe(env, email);
    return json({ ok: false, error: "subscribe_failed" }, 502, headers);
  }

  return json({ ok: true }, 200, headers);
}

async function handleCorrections(request, env, headers) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false }, 400, headers);
  }

  const hp = String(body.hp || body.website || "").trim();
  if (hp) {
    return json({ ok: false }, 400, headers);
  }

  const suggestion = String(body.suggestion || body.message || "").trim();
  const topicSlug = String(body.topic_slug || "").trim();
  const pageUrl = String(body.page_url || "").trim();
  const edition = String(body.edition || "").trim();

  if (!suggestion || suggestion.length < 8) {
    return json({ ok: false, error: "short_message" }, 400, headers);
  }
  if (suggestion.length > 4000) {
    return json({ ok: false, error: "long_message" }, 400, headers);
  }
  if (!topicSlug) {
    return json({ ok: false, error: "missing_slug" }, 400, headers);
  }
  if (!pageUrl && !edition) {
    return json({ ok: false, error: "missing_context" }, 400, headers);
  }

  const kind = CORRECTION_KINDS.has(body.kind) ? body.kind : "other";
  const articleNum = String(body.article_num || "").trim();
  const articleTitle = String(body.article_title || "").trim().slice(0, 300);
  const quoted = String(body.quoted || body.selected_text || "").trim().slice(0, 800);
  const replyEmail = String(body.email || "").trim();
  if (replyEmail && !replyEmail.includes("@")) {
    return json({ ok: false }, 400, headers);
  }

  const rate = await enforceCorrectionRateLimit(request, env);
  if (!rate.ok) {
    return json(
      { ok: false, error: "rate_limited" },
      429,
      { ...headers, "Retry-After": String(rate.retryAfter) },
    );
  }

  const sent = await notifyCorrection(env, {
    edition,
    pageUrl,
    topicSlug,
    articleNum,
    articleTitle,
    kind,
    quoted,
    suggestion,
    replyEmail,
  });
  if (sent === null) {
    return json({ ok: false, error: "misconfigured" }, 500, headers);
  }
  if (!sent) {
    return json({ ok: false, error: "send_failed" }, 502, headers);
  }

  return json({ ok: true }, 200, headers);
}

async function enforceCorrectionRateLimit(request, env) {
  const kv = rateLimitKv(env);
  if (!kv) return { ok: true };

  const ip = clientIp(request);
  const ipMax = parseInt(env.CORRECTIONS_RATE_LIMIT_IP_MAX || "5", 10);
  const ipWindow = parseInt(env.CORRECTIONS_RATE_LIMIT_IP_WINDOW || "3600", 10);
  return await consumeRateLimit(kv, `corr-ip:${ip}`, ipMax, ipWindow);
}

function kindLabel(kind) {
  if (kind === "factual") return "Faktická chyba";
  if (kind === "typo") return "Překlep / formulace";
  return "Jiné";
}

function resendFrom(env) {
  const email = (env.RESEND_FROM_EMAIL || env.ECOMAIL_FROM_EMAIL || "").trim();
  const name = (env.RESEND_FROM_NAME || "Poslušně hlásím").trim();
  if (!email) return "";
  return `${name} <${email}>`;
}

function correctionsNotifyEmail(env) {
  return (env.CORRECTIONS_NOTIFY_EMAIL || env.NOTIFY_EMAIL || env.ECOMAIL_FROM_EMAIL || "").trim();
}

async function sendResendEmail(env, { to, subject, text, html, replyTo }) {
  const apiKey = (env.RESEND_API_KEY || "").trim();
  const from = resendFrom(env);
  if (!apiKey || !from || !to) return null;

  const body = {
    from,
    to: [to],
    subject: subject.slice(0, 120),
    text,
    html,
  };
  if (replyTo) body.reply_to = replyTo;

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      "User-Agent": "poslusnehlasim-workers/1.0",
    },
    body: JSON.stringify(body),
  });

  return res.ok;
}

async function notifyCorrection(env, payload) {
  const to = correctionsNotifyEmail(env);
  if (!to || !(env.RESEND_API_KEY || "").trim() || !resendFrom(env)) return null;

  const lines = [
    "Nový návrh korektury k článku v novinách.",
    "",
    payload.edition ? `Vydání: ${payload.edition}` : "",
    payload.pageUrl ? `URL: ${payload.pageUrl}` : "",
    payload.articleNum
      ? `Článek: ${payload.articleNum}${payload.articleTitle ? `, ${payload.articleTitle}` : ""}`
      : payload.articleTitle
        ? `Článek: ${payload.articleTitle}`
        : "",
    `Slug: ${payload.topicSlug}`,
    `Typ: ${kindLabel(payload.kind)}`,
    payload.quoted ? `Označený text: ${payload.quoted}` : "",
    "",
    "Návrh:",
    payload.suggestion,
    "",
    payload.replyEmail ? `Kontakt na odesílatele: ${payload.replyEmail}` : "Kontakt: neuveden",
  ].filter(Boolean);

  const subjectBits = [payload.articleNum, payload.topicSlug].filter(Boolean);
  const subject = `Korektura: ${subjectBits.join(" · ") || "noviny"}`;

  const esc = (s) =>
    String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const htmlParts = lines.map((line) => `<p>${esc(line)}</p>`).join("");

  return sendResendEmail(env, {
    to,
    subject,
    text: lines.join("\n"),
    html: htmlParts,
    replyTo: payload.replyEmail || undefined,
  });
}

function clientIp(request) {
  const cf = request.headers.get("CF-Connecting-IP");
  if (cf) return cf;
  const xff = request.headers.get("X-Forwarded-For");
  if (xff) return xff.split(",")[0].trim();
  return "unknown";
}

function rateLimitKv(env) {
  const kv = env.RATE_LIMIT;
  if (!kv) return null;
  const id = env.RATE_LIMIT_ID || "";
  if (id === RATE_LIMIT_PLACEHOLDER) return null;
  return kv;
}

async function enforceRateLimits(request, env, email) {
  const kv = rateLimitKv(env);
  if (!kv) return { ok: true };

  const ip = clientIp(request);
  const ipMax = parseInt(env.RATE_LIMIT_IP_MAX || "10", 10);
  const ipWindow = parseInt(env.RATE_LIMIT_IP_WINDOW || "3600", 10);
  const emailMax = parseInt(env.RATE_LIMIT_EMAIL_MAX || "3", 10);
  const emailWindow = parseInt(env.RATE_LIMIT_EMAIL_WINDOW || "86400", 10);

  const ipCheck = await consumeRateLimit(kv, `ip:${ip}`, ipMax, ipWindow);
  if (!ipCheck.ok) return ipCheck;

  const normalized = email.toLowerCase();
  return await consumeRateLimit(kv, `email:${normalized}`, emailMax, emailWindow);
}

async function consumeRateLimit(kv, key, limit, windowSec) {
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - (now % windowSec);
  const kvKey = `rl:${key}:${windowStart}`;

  const raw = await kv.get(kvKey);
  const count = raw ? parseInt(raw, 10) : 0;
  if (count >= limit) {
    const retryAfter = windowStart + windowSec - now;
    return { ok: false, retryAfter: Math.max(1, retryAfter) };
  }

  await kv.put(kvKey, String(count + 1), { expirationTtl: windowSec + 120 });
  return { ok: true };
}

async function notifyAdminSubscribe(env, failedEmail) {
  const to = (env.NOTIFY_EMAIL || env.ECOMAIL_FROM_EMAIL || "").trim();
  const from = (env.ECOMAIL_FROM_EMAIL || to).trim();
  if (!to || !from || !env.ECOMAIL_API_KEY) return;

  const kv = rateLimitKv(env);
  const normalized = failedEmail.toLowerCase();
  const dedupeTtl = parseInt(env.NOTIFY_DEDUPE_WINDOW || "86400", 10);
  if (kv) {
    const dedupeKey = `admin-notify:${normalized}`;
    if (await kv.get(dedupeKey)) return;
    await kv.put(dedupeKey, "1", { expirationTtl: dedupeTtl });
  }

  const safe = failedEmail.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  await fetch("https://api2.ecomailapp.cz/transactional/send-message", {
    method: "POST",
    headers: {
      key: env.ECOMAIL_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: {
        subject: "Neúspěšný odběr novinek",
        from_name: "Poslušně hlásím",
        from_email: from,
        text: `E-mail ${failedEmail} se nepodařilo zapsat do odběru novinek.`,
        html: `<p>E-mail <strong>${safe}</strong> se nepodařilo zapsat do odběru novinek.</p>`,
        to: [{ email: to }],
        options: { click_tracking: false, open_tracking: false },
      },
    }),
  });
}

function json(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}

function subscribeListId(env) {
  return env.ECOMAIL_SUBSCRIBE_LIST_ID || env.ECOMAIL_LIST_ID || "3";
}
