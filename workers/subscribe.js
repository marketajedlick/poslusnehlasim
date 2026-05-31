/** Cloudflare Worker — odběr novinek přes Ecomail API (bez robotchecku ve formuláři). */

const CORS = {
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

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
    if (!env.ECOMAIL_API_KEY || !env.ECOMAIL_LIST_ID) {
      return json({ ok: false, error: "misconfigured" }, 500, headers);
    }

    const res = await fetch(
      `https://api2.ecomailapp.cz/lists/${env.ECOMAIL_LIST_ID}/subscribe`,
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
        }),
      },
    );

    if (!res.ok) {
      const text = await res.text();
      return json({ ok: false, error: text.slice(0, 200) }, 502, headers);
    }

    return json({ ok: true }, 200, headers);
  },
};

function json(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}
