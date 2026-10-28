/** Cloudflare Worker: odběr novinek (Ecomail + Resend DOI) + návrhy korektur (Resend). */

const CORS = {
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
};

const RATE_LIMIT_PLACEHOLDER = "00000000000000000000000000000000";

const CORRECTION_KINDS = new Set(["factual", "typo", "other"]);
const REACTION_TYPES = new Set(["absurdni", "tosnadne", "libi", "potlesk", "nojo"]);
const REACTION_DEFAULTS = { absurdni: 0, tosnadne: 0, libi: 0, potlesk: 0, nojo: 0 };
const EDITION_RE = /^\d{4}-\d{2}-\d{2}$/;
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,119}$/i;
const DOI_TEMPLATE_NAME = "Poslušně hlásím · DOI";
const SUBCONFIRM_TAG = "*|SUBCONFIRM|*";

export default {
  async fetch(request, env) {
    const headers = responseHeaders(request, env);
    try {
      return await route(request, env, headers);
    } catch (err) {
      // Typicky vyčerpaná kvóta KV nebo výpadek Ecomailu/Resendu: vrátit 503, ne 1101.
      console.error("unhandled", err && err.stack ? err.stack : String(err));
      return json({ ok: false, error: "unavailable" }, 503, headers);
    }
  },
};

async function route(request, env, headers) {
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

  if (path === "/reactions") {
    if (request.method === "GET") {
      return handleReactionsGet(request, env, headers);
    }
    if (request.method === "POST") {
      return handleReactionsPost(request, env, headers);
    }
    return new Response("Method not allowed", { status: 405, headers });
  }

  if (path === "/confirm") {
    // GET jen ukáže tlačítko: skenery odkazů (Safe Links apod.) dělají GET
    // a nesmí odběr potvrdit za člověka. Potvrzuje až POST z formuláře.
    if (request.method === "GET") {
      return handleConfirmPage(request, env);
    }
    if (request.method === "POST") {
      return handleConfirm(request, env);
    }
    return new Response("Method not allowed", { status: 405, headers });
  }

  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers });
  }
  return handleSubscribe(request, env, headers);
}

function responseHeaders(request, env) {
  const allowed = (env.ALLOWED_ORIGIN || "https://poslusnehlasim.cz")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const requestOrigin = request.headers.get("Origin") || "";
  const corsOrigin =
    requestOrigin && allowed.includes(requestOrigin) ? requestOrigin : allowed[0];
  return { ...SECURITY_HEADERS, ...CORS, "Access-Control-Allow-Origin": corsOrigin };
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
  if (hp || !validSubscribeEmail(email)) {
    return json({ ok: false }, 400, headers);
  }
  const listId = subscribeListId(env);
  if (!env.ECOMAIL_API_KEY || !listId) {
    return json({ ok: false, error: "misconfigured" }, 500, headers);
  }
  if (!(env.RESEND_API_KEY || "").trim() || !resendFrom(env)) {
    return json({ ok: false, error: "misconfigured" }, 500, headers);
  }

  if (body.notify_failed) {
    return json({ ok: false }, 400, headers);
  }

  if (!(await verifyTurnstile(request, env, body))) {
    return json({ ok: false, error: "captcha_failed" }, 403, headers);
  }

  const rate = await enforceRateLimits(request, env, email);
  if (!rate.ok) {
    return json(
      { ok: false, error: "rate_limited" },
      429,
      { ...headers, "Retry-After": String(rate.retryAfter) },
    );
  }

  const current = await getSubscriberStatus(env, listId, email);
  if (!current.ok) {
    // Neznámý stav: zápis se status 6 + update_existing by potvrzeného
    // odběratele shodil na nepotvrzeného. Radši nic neměnit.
    console.error("subscriber_status_unavailable", email);
    return json({ ok: false, error: "subscribe_failed" }, 503, headers);
  }
  if (current.status === 1) {
    return json({ ok: true }, 200, headers);
  }

  let subscribed = await subscribeToEcomail(env, listId, email, { resubscribe: true });
  if (!subscribed.ok) {
    await notifyAdminSubscribe(env, email);
    return json({ ok: false, error: "subscribe_failed" }, 502, headers);
  }

  // Už potvrzený odběratel — formulář ukáže stejnou zprávu, mail znovu neposíláme.
  if (subscribed.status === 1) {
    return json({ ok: true }, 200, headers);
  }

  const daily = await enforceDoiDailyCap(env);
  if (!daily.ok) {
    console.error("doi_daily_cap_reached");
    return json(
      { ok: false, error: "rate_limited" },
      429,
      { ...headers, "Retry-After": String(daily.retryAfter) },
    );
  }

  const sent = await sendDoiViaResend(env, {
    listId,
    email,
    workerOrigin: workerOrigin(request, env),
  });
  if (sent === null) {
    return json({ ok: false, error: "misconfigured" }, 500, headers);
  }
  if (!sent.ok) {
    console.error("doi_resend_failed", email, sent.error);
    await notifyAdminSubscribe(env, email, "doi_resend_failed", sent.error);
    return json({ ok: false, error: "send_failed" }, 502, headers);
  }

  return json({ ok: true }, 200, headers);
}

function ecomailHeaders(env) {
  return {
    key: env.ECOMAIL_API_KEY,
    "Content-Type": "application/json",
  };
}

/** {ok: true, status} — status 0 = v seznamu není; {ok: false} = stav nejde zjistit. */
async function getSubscriberStatus(env, listId, email) {
  let res;
  try {
    res = await fetch(
      `https://api2.ecomailapp.cz/lists/${listId}/subscriber/${encodeURIComponent(email)}`,
      { headers: ecomailHeaders(env) },
    );
  } catch {
    return { ok: false };
  }
  if (res.status === 404) return { ok: true, status: 0 };
  if (!res.ok) return { ok: false };
  let data = {};
  try {
    data = await res.json();
  } catch {
    return { ok: false };
  }
  const nested =
    data.subscriber && typeof data.subscriber === "object" ? data.subscriber : null;
  const status = Number(data.status ?? nested?.status);
  return Number.isFinite(status) ? { ok: true, status } : { ok: false };
}

async function subscribeToEcomail(env, listId, email, { resubscribe }) {
  const res = await fetch(`https://api2.ecomailapp.cz/lists/${listId}/subscribe`, {
    method: "POST",
    headers: ecomailHeaders(env),
    body: JSON.stringify({
      subscriber_data: { email, source: "poslusnehlasim", status: 6 },
      trigger_autoresponders: false,
      update_existing: true,
      resubscribe,
      skip_confirmation: true,
    }),
  });
  if (!res.ok) {
    return { ok: false };
  }
  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  return {
    ok: true,
    status: Number(data.status),
    already_subscribed: Boolean(data.already_subscribed),
  };
}

function confirmRedirectUrl(env) {
  return (env.CONFIRM_REDIRECT_URL || "https://poslusnehlasim.cz/potvrzeno/").trim();
}

function privacyUrl(env) {
  return (env.SVEJK_PRIVACY_URL || "https://poslusnehlasim.cz/soukromi/").trim();
}

function workerOrigin(request, env) {
  const configured = (env.SUBSCRIBE_PUBLIC_URL || "").trim();
  if (configured) return configured.replace(/\/+$/, "");
  return new URL(request.url).origin;
}

function doiTemplateCacheTtl(env) {
  return parseInt(env.DOI_TEMPLATE_CACHE_TTL || "3600", 10);
}

function doiTokenTtl(env) {
  return parseInt(env.DOI_TOKEN_TTL || "604800", 10);
}

function templateUsable(html) {
  if (!html || !html.trim()) return false;
  return (
    html.includes(SUBCONFIRM_TAG) ||
    /class=["']email-cta["']/i.test(html) ||
    /\*\|SUBCONFIRM\|\*/i.test(html)
  );
}

const ECOMAIL_OPTIN_HREF_RE =
  /https?:\/\/[^/"'\s>]+\.ecomailapp\.cz\/public\/optin\/[^"'\s>]*/gi;

function injectConfirmUrl(html, confirmUrl) {
  let out = html;
  if (out.includes(SUBCONFIRM_TAG)) {
    out = out.split(SUBCONFIRM_TAG).join(confirmUrl);
  }
  out = out.replace(ECOMAIL_OPTIN_HREF_RE, confirmUrl);
  out = out.replace(
    /(<a\b[^>]*class=["']email-cta["'][^>]*href=["'])[^"']*(["'])/gi,
    `$1${confirmUrl}$2`,
  );
  out = out.replace(
    /(<a\b[^>]*href=["'])[^"']*(["'][^>]*class=["']email-cta["'])/gi,
    `$1${confirmUrl}$2`,
  );
  out = out.replace(/(<v:roundrect\b[^>]*href=["'])[^"']*(["'])/gi, `$1${confirmUrl}$2`);
  return out;
}

function fallbackDoiTemplate(env) {
  const privacy = privacyUrl(env);
  return {
    subject: "Poslušně hlásím: potvrď odběr novinek",
    html: `<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8"><title>Potvrď odběr</title></head><body style="margin:0;padding:24px;background:#f7f2f0;font-family:Georgia,serif;color:#262626;"><div style="max-width:600px;margin:0 auto;text-align:center;"><p style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:#6b6355;">Deník sněmovny</p><h1 style="font-family:Arial,sans-serif;font-size:42px;line-height:1;color:#262626;">Poslušně hlásím!</h1><p style="font-size:17px;line-height:1.55;">Deník sněmovny už čeká. Ještě je ale třeba jeden krok. Potvrď, že e-mail patří opravdu tobě a chceš deník odebírat.</p><p style="margin:28px 0;"><a href="${SUBCONFIRM_TAG}" class="email-cta" style="display:inline-block;background:#ff4411;color:#ffffff;font-family:Arial,sans-serif;font-weight:bold;text-transform:uppercase;text-decoration:none;padding:15px 36px;border-radius:3px;">Potvrdit odběr</a></p><p style="font-size:13px;color:#6b6355;">Až přijde první vydání, může skončit ve složce Hromadné. Přetáhni ho do Primárních - stačí jednou a Gmail si to zapamatuje.</p><p style="font-size:12px;color:#5a503e;">Pokud tento e-mail přišel omylem, není třeba nic dělat.<br><a href="${privacy}" style="color:#5a503e;">Co děláme s e-mailovou adresou.</a></p></div></body></html>`,
    source: "fallback",
  };
}

async function getDoiTemplateFromLibrary(env) {
  const res = await fetch("https://api2.ecomailapp.cz/templates", {
    headers: ecomailHeaders(env),
  });
  if (!res.ok) return null;

  let templates = [];
  try {
    templates = await res.json();
  } catch {
    return null;
  }
  if (!Array.isArray(templates)) return null;

  const hit = templates.find((t) => (t.name || "").trim() === DOI_TEMPLATE_NAME);
  if (!hit?.id) return null;

  const detailRes = await fetch(`https://api2.ecomailapp.cz/templates/${hit.id}`, {
    headers: ecomailHeaders(env),
  });
  if (!detailRes.ok) return null;

  let detail = {};
  try {
    detail = await detailRes.json();
  } catch {
    return null;
  }

  const html = String(detail.html || "");
  if (!templateUsable(html)) return null;
  return {
    subject: "Poslušně hlásím: potvrď odběr novinek",
    html,
    source: "library",
  };
}

async function getDoiTemplate(env, listId) {
  const kv = rateLimitKv(env);
  const cacheKey = `doi-conf:${listId}`;
  if (kv) {
    const cached = await kv.get(cacheKey).catch(() => null);
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch {
        /* ignore */
      }
    }
  }

  let tpl = null;

  const res = await fetch(`https://api2.ecomailapp.cz/lists/${listId}`, {
    headers: ecomailHeaders(env),
  });
  if (res.ok) {
    let data = {};
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    const list = data.list && typeof data.list === "object" ? data.list : data;
    const subject = String(list.conf_subject || "Poslušně hlásím: potvrď odběr novinek").trim();
    const html = String(list.conf_message || "");
    if (templateUsable(html)) {
      tpl = { subject, html, source: "list" };
    }
  }

  if (!tpl) {
    tpl = await getDoiTemplateFromLibrary(env);
  }
  if (!tpl) {
    tpl = fallbackDoiTemplate(env);
  }

  if (kv) {
    await kv
      .put(cacheKey, JSON.stringify(tpl), {
        expirationTtl: doiTemplateCacheTtl(env) + 120,
      })
      .catch((err) => console.error("doi_template_cache_put_failed", String(err)));
  }
  return tpl;
}

function buildDoiPlain(confirmUrl, env) {
  const redirect = confirmRedirectUrl(env);
  const privacy = privacyUrl(env);
  return [
    "POSLUŠNĚ HLÁSÍM: potvrď odběr novinek",
    "",
    "Deník sněmovny už čeká. Ještě je ale třeba jeden krok. Potvrď, že e-mail patří opravdu tobě a chceš deník odebírat.",
    "",
    "Poslušně hlásím, že bez potvrzení ti nemůžeme poslat ani řádku. Klikni a je vyřízeno.",
    "",
    `Potvrď odběr: ${confirmUrl}`,
    "",
    "Až přijde první vydání, může skončit ve složce Hromadné. Přetáhni ho do Primárních - stačí jednou a Gmail si to zapamatuje.",
    "",
    `Po potvrzení tě přesměrujeme na: ${redirect}`,
    "Pokud tento e-mail přišel omylem, není třeba nic dělat.",
    `Co děláme s e-mailovou adresou.: ${privacy}`,
  ].join("\n");
}

async function storeConfirmToken(env, token, email, listId) {
  const kv = rateLimitKv(env);
  if (!kv) return false;
  await kv.put(
    `doi-token:${token}`,
    JSON.stringify({ email: email.toLowerCase(), listId: String(listId) }),
    { expirationTtl: doiTokenTtl(env) },
  );
  return true;
}

async function sendDoiViaResend(env, { listId, email, workerOrigin }) {
  const tpl = await getDoiTemplate(env, listId);

  const token = crypto.randomUUID();
  if (!(await storeConfirmToken(env, token, email, listId))) return null;

  const confirmUrl = `${workerOrigin}/confirm?token=${encodeURIComponent(token)}`;
  const html = injectConfirmUrl(tpl.html, confirmUrl);
  const plain = buildDoiPlain(confirmUrl, env);

  return sendResendEmail(env, {
    to: email,
    subject: tpl.subject,
    text: plain,
    html,
  });
}

async function confirmSubscriber(env, listId, email) {
  const res = await fetch(`https://api2.ecomailapp.cz/lists/${listId}/subscribe`, {
    method: "POST",
    headers: ecomailHeaders(env),
    body: JSON.stringify({
      subscriber_data: { email, status: 1 },
      trigger_autoresponders: false,
      update_existing: true,
      resubscribe: true,
      skip_confirmation: true,
    }),
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.text()).slice(0, 300);
    } catch {
      detail = "";
    }
    console.error("confirm_subscribe_failed", email, res.status, detail);
  }

  let status = (await getSubscriberStatus(env, listId, email)).status;
  if (status === 1) return true;

  const bulkRes = await fetch(`https://api2.ecomailapp.cz/lists/${listId}/update-subscribers-bulk`, {
    method: "PUT",
    headers: ecomailHeaders(env),
    body: JSON.stringify({
      subscriber_data: [{ email, status: 1 }],
      allow_resubscribe: true,
    }),
  });
  if (!bulkRes.ok) {
    let detail = "";
    try {
      detail = (await bulkRes.text()).slice(0, 300);
    } catch {
      detail = "";
    }
    console.error("confirm_bulk_failed", email, bulkRes.status, detail);
    return false;
  }

  status = (await getSubscriberStatus(env, listId, email)).status;
  if (status !== 1) {
    console.error("confirm_status_still", email, status);
  }
  return status === 1;
}

const CONFIRM_PAGE_HEADERS = {
  ...SECURITY_HEADERS,
  "Content-Security-Policy":
    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store",
};

function confirmPage(title, bodyHtml, status = 200) {
  const html = `<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${title}</title></head><body style="margin:0;padding:48px 24px;background:#f7f2f0;font-family:Georgia,serif;color:#262626;"><div style="max-width:520px;margin:0 auto;text-align:center;"><h1 style="font-family:Arial,sans-serif;font-size:32px;line-height:1.1;">${title}</h1>${bodyHtml}</div></body></html>`;
  return new Response(html, { status, headers: CONFIRM_PAGE_HEADERS });
}

function confirmTokenFrom(url) {
  return url.searchParams.get("token")?.trim() || "";
}

async function loadConfirmToken(kv, token) {
  const raw = await kv.get(`doi-token:${token}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function handleConfirmPage(request, env) {
  const token = confirmTokenFrom(new URL(request.url));
  if (!token) {
    return confirmPage("Chybí token", "<p>Odkaz je neúplný.</p>", 400);
  }
  const kv = rateLimitKv(env);
  if (!kv) {
    return confirmPage("Služba není nakonfigurována", "", 503);
  }
  // Token se tu jen ověří, nespotřebuje — to až POST.
  if (!(await loadConfirmToken(kv, token))) {
    return confirmPage("Odkaz vypršel", "<p>Odkaz vypršel nebo už byl použit.</p>", 410);
  }
  const safeToken = token.replace(/[^A-Za-z0-9-]/g, "");
  return confirmPage(
    "Potvrď odběr",
    `<p style="font-size:17px;line-height:1.55;">Ještě jedno kliknutí a deník sněmovny ti začne chodit do schránky.</p><form method="POST" action="/confirm?token=${encodeURIComponent(safeToken)}" style="margin:28px 0;"><button type="submit" style="background:#ff4411;color:#fff;border:0;font-family:Arial,sans-serif;font-weight:bold;text-transform:uppercase;padding:15px 36px;border-radius:3px;font-size:16px;cursor:pointer;">Potvrdit odběr</button></form><p style="font-size:13px;color:#6b6355;">Pokud jsi o odběr nežádal(a), stránku zavři. Nic se nestane.</p>`,
  );
}

async function handleConfirm(request, env) {
  const token = confirmTokenFrom(new URL(request.url));
  if (!token) {
    return new Response("Chybí token.", { status: 400, headers: SECURITY_HEADERS });
  }

  const kv = rateLimitKv(env);
  if (!kv) {
    return new Response("Služba není nakonfigurována.", {
      status: 503,
      headers: SECURITY_HEADERS,
    });
  }

  const payload = await loadConfirmToken(kv, token);
  if (!payload) {
    return confirmPage("Odkaz vypršel", "<p>Odkaz vypršel nebo už byl použit.</p>", 410);
  }

  const email = String(payload.email || "").trim();
  const listId = payload.listId || subscribeListId(env);
  if (!email || !env.ECOMAIL_API_KEY || !listId) {
    return new Response("Služba není nakonfigurována.", {
      status: 503,
      headers: SECURITY_HEADERS,
    });
  }

  const ok = await confirmSubscriber(env, listId, email);
  if (!ok) {
    return confirmPage(
      "Potvrzení se nepodařilo",
      "<p>Zkus to prosím znovu z odkazu v mailu.</p>",
      502,
    );
  }

  await kv.delete(`doi-token:${token}`);
  // 303: po POST přejít na GET stránku potvrzení.
  return Response.redirect(confirmRedirectUrl(env), 303);
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

  if (!suggestion) {
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
  const ipMax = parseInt(env.CORRECTIONS_RATE_LIMIT_IP_MAX || "20", 10);
  const ipWindow = parseInt(env.CORRECTIONS_RATE_LIMIT_IP_WINDOW || "3600", 10);
  return await consumeRateLimit(kv, `corr-ip:${ip}`, ipMax, ipWindow);
}

function parseReactionCounts(raw) {
  const counts = { ...REACTION_DEFAULTS };
  if (!raw) return counts;
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return counts;
  }
  if (!data || typeof data !== "object") return counts;
  for (const key of REACTION_TYPES) {
    const n = Number(data[key]);
    if (Number.isFinite(n) && n > 0) counts[key] = Math.floor(n);
  }
  return counts;
}

function validEdition(edition) {
  return EDITION_RE.test(edition);
}

function validSlug(slug) {
  return SLUG_RE.test(slug);
}

function reactionKvKey(edition, slug) {
  return `rx:${edition}:${slug}`;
}

/** Všechny reakce vydání v jednom klíči: GET = 1 čtení, žádné kv.list (kvóta). */
function reactionEditionKey(edition) {
  return `rxe:${edition}`;
}

function parseEditionReactions(raw) {
  if (!raw) return null;
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const out = {};
  for (const [slug, counts] of Object.entries(data)) {
    if (validSlug(slug)) out[slug] = parseReactionCounts(JSON.stringify(counts));
  }
  return out;
}

async function loadEditionReactions(kv, edition) {
  const stored = parseEditionReactions(await kv.get(reactionEditionKey(edition)));
  if (stored) return { articles: stored, migrated: false };
  // Starší formát (klíč na článek): jednou načíst přes list a uložit do souhrnného klíče.
  const prefix = `rx:${edition}:`;
  const articles = {};
  let cursor;
  do {
    const page = await kv.list({ prefix, cursor });
    for (const item of page.keys) {
      const slug = item.name.slice(prefix.length);
      if (!validSlug(slug)) continue;
      articles[slug] = parseReactionCounts(await kv.get(item.name));
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return { articles, migrated: true };
}

function reactionsCacheKey(request, edition) {
  const url = new URL(request.url);
  return new Request(`${url.origin}/reactions?edition=${edition}`, { method: "GET" });
}

async function handleReactionsGet(request, env, headers) {
  const edition = new URL(request.url).searchParams.get("edition")?.trim() || "";
  if (!edition) {
    return json({ ok: true, service: "reactions" }, 200, headers);
  }
  if (!validEdition(edition)) {
    return json({ ok: false, error: "bad_edition" }, 400, headers);
  }

  const kv = rateLimitKv(env);
  if (!kv) {
    return json({ ok: false, error: "misconfigured" }, 503, headers);
  }

  const ttl = parseInt(env.REACTIONS_CACHE_TTL || "60", 10);
  const cache = typeof caches !== "undefined" ? caches.default : null;
  const cacheKey = reactionsCacheKey(request, edition);
  if (cache) {
    const hit = await cache.match(cacheKey).catch(() => null);
    if (hit) {
      const data = await hit.json().catch(() => null);
      if (data) return json(data, 200, { ...headers, "Cache-Control": `public, max-age=${ttl}` });
    }
  }

  let articles = {};
  try {
    const loaded = await loadEditionReactions(kv, edition);
    articles = loaded.articles;
    if (loaded.migrated) {
      await kv.put(reactionEditionKey(edition), JSON.stringify(articles));
    }
  } catch (err) {
    // Kvóta KV: reakce nejsou kritické, stránka má fungovat dál.
    console.error("reactions_get_kv_failed", String(err));
    return json({ ok: true, edition, articles: {}, degraded: true }, 200, headers);
  }

  const data = { ok: true, edition, articles };
  if (cache) {
    const cached = new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json", "Cache-Control": `public, max-age=${ttl}` },
    });
    await cache.put(cacheKey, cached).catch(() => {});
  }
  return json(data, 200, { ...headers, "Cache-Control": `public, max-age=${ttl}` });
}

async function handleReactionsPost(request, env, headers) {
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

  const edition = String(body.edition || "").trim();
  const slug = String(body.slug || body.topic_slug || "").trim();
  const reaction = String(body.reaction || "").trim();
  const previous = String(body.previous || "").trim();
  const clear = body.clear === true || reaction === "clear";

  if (!validEdition(edition) || !validSlug(slug)) {
    return json({ ok: false, error: "bad_request" }, 400, headers);
  }

  if (clear) {
    if (!REACTION_TYPES.has(previous)) {
      return json({ ok: false, error: "bad_previous" }, 400, headers);
    }
  } else {
    if (!REACTION_TYPES.has(reaction)) {
      return json({ ok: false, error: "bad_reaction" }, 400, headers);
    }
    if (previous && (!REACTION_TYPES.has(previous) || previous === reaction)) {
      return json({ ok: false, error: "bad_previous" }, 400, headers);
    }
  }

  const rate = await enforceReactionRateLimit(request, env);
  if (!rate.ok) {
    return json(
      { ok: false, error: "rate_limited" },
      429,
      { ...headers, "Retry-After": String(rate.retryAfter) },
    );
  }

  const kv = rateLimitKv(env);
  if (!kv) {
    return json({ ok: false, error: "misconfigured" }, 503, headers);
  }

  let counts;
  try {
    const { articles } = await loadEditionReactions(kv, edition);
    counts = articles[slug] || { ...REACTION_DEFAULTS };

    if (clear) {
      counts[previous] = Math.max(0, (counts[previous] || 0) - 1);
    } else {
      if (previous) {
        counts[previous] = Math.max(0, (counts[previous] || 0) - 1);
      }
      counts[reaction] = (counts[reaction] || 0) + 1;
    }
    articles[slug] = counts;
    await kv.put(reactionEditionKey(edition), JSON.stringify(articles));
  } catch (err) {
    console.error("reactions_post_kv_failed", String(err));
    return json({ ok: false, error: "unavailable" }, 503, headers);
  }
  if (typeof caches !== "undefined") {
    await caches.default.delete(reactionsCacheKey(request, edition)).catch(() => {});
  }

  return json({ ok: true, edition, slug, counts }, 200, headers);
}

async function enforceReactionRateLimit(request, env) {
  const ip = clientIp(request);
  // Binding Rate Limiting (atomický, nežere KV zápisy), když je nasazený.
  if (env.REACTIONS_LIMITER) {
    return await bindingLimit(env.REACTIONS_LIMITER, `rx-ip:${ip}`);
  }
  const kv = rateLimitKv(env);
  if (!kv) return { ok: true };

  const ipMax = parseInt(env.REACTIONS_RATE_LIMIT_IP_MAX || "60", 10);
  const ipWindow = parseInt(env.REACTIONS_RATE_LIMIT_IP_WINDOW || "3600", 10);
  return await consumeRateLimit(kv, `rx-ip:${ip}`, ipMax, ipWindow);
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

  if (res.ok) return { ok: true };
  let detail = "";
  try {
    detail = (await res.text()).slice(0, 300);
  } catch {
    detail = "";
  }
  return { ok: false, error: `${res.status}${detail ? `: ${detail}` : ""}` };
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

  const message = { to, subject, text: lines.join("\n"), html: htmlParts };
  const replyTo = REPLY_EMAIL_RE.test(payload.replyEmail || "") ? payload.replyEmail : undefined;
  let sent = await sendResendEmail(env, { ...message, replyTo });
  if (sent && !sent.ok && replyTo && String(sent.error).startsWith("422")) {
    // Resend odmítne nevalidní reply_to; kontakt je i v textu, takže návrh neztrácíme.
    console.error("correction_reply_to_rejected", sent.error);
    sent = await sendResendEmail(env, message);
  }
  return sent?.ok === true;
}

const REPLY_EMAIL_RE = /^[^\s@<>,;"]+@[^\s@<>,;"]+\.[^\s@<>,;"]{2,}$/;

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
  const ip = clientIp(request);
  if (env.SUBSCRIBE_LIMITER) {
    const bound = await bindingLimit(env.SUBSCRIBE_LIMITER, `ip:${ip}`);
    if (!bound.ok) return bound;
  }

  const kv = rateLimitKv(env);
  if (!kv) return { ok: true };

  const ipMax = parseInt(env.RATE_LIMIT_IP_MAX || "10", 10);
  const ipWindow = parseInt(env.RATE_LIMIT_IP_WINDOW || "3600", 10);
  const emailMax = parseInt(env.RATE_LIMIT_EMAIL_MAX || "3", 10);
  const emailWindow = parseInt(env.RATE_LIMIT_EMAIL_WINDOW || "86400", 10);

  const ipCheck = await consumeRateLimit(kv, `ip:${ip}`, ipMax, ipWindow);
  if (!ipCheck.ok) return ipCheck;

  const normalized = email.toLowerCase();
  return await consumeRateLimit(kv, `email:${normalized}`, emailMax, emailWindow);
}

/** KV limit je jen přibližný (get+put není atomický); hlavní ochrana je binding/Turnstile. */
async function consumeRateLimit(kv, key, limit, windowSec) {
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - (now % windowSec);
  const kvKey = `rl:${key}:${windowStart}`;

  let count = 0;
  try {
    const raw = await kv.get(kvKey);
    count = raw ? parseInt(raw, 10) : 0;
  } catch (err) {
    // Kvóta KV: limit neověřitelný, nepouštět kvůli tomu dolů celý odběr.
    console.error("rate_limit_kv_get_failed", key, String(err));
    return { ok: true };
  }
  if (count >= limit) {
    const retryAfter = windowStart + windowSec - now;
    return { ok: false, retryAfter: Math.max(1, retryAfter) };
  }

  try {
    await kv.put(kvKey, String(count + 1), { expirationTtl: windowSec + 120 });
  } catch (err) {
    console.error("rate_limit_kv_put_failed", key, String(err));
  }
  return { ok: true };
}

async function bindingLimit(limiter, key) {
  try {
    const { success } = await limiter.limit({ key });
    return success ? { ok: true } : { ok: false, retryAfter: 60 };
  } catch (err) {
    console.error("rate_limit_binding_failed", key, String(err));
    return { ok: true };
  }
}

/** Strop DOI mailů za den přes všechny adresy — chrání kvótu Resendu. */
async function enforceDoiDailyCap(env) {
  const kv = rateLimitKv(env);
  if (!kv) return { ok: true };
  const max = parseInt(env.DOI_DAILY_MAX || "300", 10);
  if (!(max > 0)) return { ok: true };
  return await consumeRateLimit(kv, "doi-global", max, 86400);
}

const SUBSCRIBE_EMAIL_RE = /^[^\s@<>,;"()\[\]\\]+@[^\s@<>,;"()\[\]\\]+\.[a-z]{2,}$/i;

function validSubscribeEmail(email) {
  return email.length <= 254 && SUBSCRIBE_EMAIL_RE.test(email);
}

/** Turnstile: povinné, jakmile je nastaven secret TURNSTILE_SECRET_KEY. */
async function verifyTurnstile(request, env, body) {
  const secret = (env.TURNSTILE_SECRET_KEY || "").trim();
  if (!secret) return true;
  const token = String(body.turnstile || body["cf-turnstile-response"] || "").trim();
  if (!token) return false;
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token);
  const ip = clientIp(request);
  if (ip !== "unknown") form.append("remoteip", ip);
  try {
    const res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: form,
    });
    const data = await res.json();
    return data.success === true;
  } catch (err) {
    console.error("turnstile_verify_failed", String(err));
    return false;
  }
}

async function notifyAdminSubscribe(env, failedEmail, reason = "subscribe_failed", detail = "") {
  const to = (env.NOTIFY_EMAIL || env.ECOMAIL_FROM_EMAIL || "").trim();
  if (!to || !(env.RESEND_API_KEY || "").trim() || !resendFrom(env)) return;

  const kv = rateLimitKv(env);
  const normalized = failedEmail.toLowerCase();
  const dedupeTtl = parseInt(env.NOTIFY_DEDUPE_WINDOW || "86400", 10);
  const dedupeKey = `admin-notify:${reason}:${normalized}`;
  if (kv) {
    if (await kv.get(dedupeKey)) return;
    await kv.put(dedupeKey, "1", { expirationTtl: dedupeTtl });
  }

  const safe = failedEmail.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const safeDetail = detail
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const text =
    reason === "doi_resend_failed"
      ? `E-mail ${failedEmail} je v Ecomailu, ale potvrzovací mail přes Resend se nepodařilo odeslat.${detail ? ` (${detail})` : ""}`
      : `E-mail ${failedEmail} se nepodařilo zapsat do odběru novinek.`;
  const subject =
    reason === "doi_resend_failed"
      ? "Neúspěšný potvrzovací mail (Resend)"
      : "Neúspěšný odběr novinek";
  const html =
    reason === "doi_resend_failed"
      ? `<p>E-mail <strong>${safe}</strong> je v Ecomailu, ale potvrzovací mail přes Resend se nepodařilo odeslat.${detail ? ` <code>${safeDetail}</code>` : ""}</p>`
      : `<p>E-mail <strong>${safe}</strong> se nepodařilo zapsat do odběru novinek.</p>`;
  await sendResendEmail(env, { to, subject, text, html });
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
