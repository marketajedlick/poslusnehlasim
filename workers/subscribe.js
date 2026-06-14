/** Cloudflare Worker, odběr novinek přes Ecomail API (bez robotchecku ve formuláři). */

const CORS = {
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const RATE_LIMIT_PLACEHOLDER = "00000000000000000000000000000000";

export default {
  async fetch(request, env) {
    const allowed = (env.ALLOWED_ORIGIN || "https://poslusnehlasim.cz")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const requestOrigin = request.headers.get("Origin") || "";
    const corsOrigin =
      requestOrigin && allowed.includes(requestOrigin) ? requestOrigin : allowed[0];
    const headers = { ...CORS, "Access-Control-Allow-Origin": corsOrigin };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ ok: false }, 400, headers);
    }

    const email = String(body.email || "").trim();
    const website = String(body.website || "").trim();
    if (website || !email || !email.includes("@")) {
      return json({ ok: false }, 400, headers);
    }
    const listId = env.ECOMAIL_SUBSCRIBE_LIST_ID || env.ECOMAIL_LIST_ID;
    if (!env.ECOMAIL_API_KEY || !listId) {
      return json({ ok: false, error: "misconfigured" }, 500, headers);
    }

    if (body.notify_failed) {
      // Veřejný endpoint pro admin notifikace byl zneužitelný (spam, libovolný reply_to).
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
          // Nechá Ecomail poslat DOI, kontakt skončí jako nepotvrzený (status 6).
          skip_confirmation: false,
        }),
      },
    );

    if (!res.ok) {
      const text = await res.text();
      await notifyAdmin(env, email);
      return json({ ok: false, error: text.slice(0, 200) }, 502, headers);
    }

    return json({ ok: true }, 200, headers);
  },
};

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

async function notifyAdmin(env, failedEmail) {
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
