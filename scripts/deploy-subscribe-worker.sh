#!/usr/bin/env bash
# Nasadí Cloudflare Pages worker pro odběr novinek včetně KV rate limitu.
# Vyžaduje: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, ECOMAIL_API_KEY
# Volitelně: ECOMAIL_FROM_EMAIL, NOTIFY_EMAIL
# Přepínač --github-output: při chybějících secretech tiše přeskočí a zapíše url= do GITHUB_OUTPUT

set -euo pipefail

GITHUB_OUTPUT_MODE=0
if [[ "${1:-}" == "--github-output" ]]; then
  GITHUB_OUTPUT_MODE=1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKERS_DIR="$REPO_ROOT/workers"
PROJECT=poslusnehlasim-odebir
KV_TITLE=poslusnehlasim-odebir-rl
PLACEHOLDER=00000000000000000000000000000000

write_output() {
  local url="$1"
  if [[ "$GITHUB_OUTPUT_MODE" == "1" && -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "url=$url" >> "$GITHUB_OUTPUT"
  fi
}

skip_deploy() {
  echo "$1"
  write_output ""
  exit 0
}

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  if [[ "$GITHUB_OUTPUT_MODE" == "1" ]]; then
    skip_deploy "Cloudflare API odběru přeskočeno (chybí CLOUDFLARE_API_TOKEN nebo CLOUDFLARE_ACCOUNT_ID)"
  fi
  echo "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID chybí — API odběru se nenasadí."
  echo "Viz DEPLOY.md → Odběr z webu (Cloudflare Worker)."
  exit 0
fi

if [[ -z "${ECOMAIL_API_KEY:-}" ]]; then
  if [[ "$GITHUB_OUTPUT_MODE" == "1" ]]; then
    skip_deploy "Cloudflare API odběru přeskočeno (chybí ECOMAIL_API_KEY)"
  fi
  echo "ECOMAIL_API_KEY chybí — API bez klíče nedává smysl."
  exit 0
fi

cd "$WORKERS_DIR"

npx wrangler@4 pages project create "$PROJECT" --production-branch=main 2>/dev/null || true

resolve_kv_id() {
  npx wrangler@4 kv namespace list 2>/dev/null | node -e "
    const title = process.argv[1];
    const raw = require('fs').readFileSync(0, 'utf8');
    try {
      const list = JSON.parse(raw || '[]');
      const ns = list.find((n) => n.title === title);
      if (ns?.id) process.stdout.write(ns.id);
    } catch {}
  " "$KV_TITLE"
}

parse_kv_id_from_text() {
  node -e "
    const t = require('fs').readFileSync(0, 'utf8');
    const m = t.match(/id = \"([^\"]+)\"/);
    process.stdout.write(m ? m[1] : '');
  "
}

KV_ID="$(resolve_kv_id)"

if [[ -z "$KV_ID" ]]; then
  CREATE_OUT=$(npx wrangler@4 kv namespace create "$KV_TITLE" 2>&1) || true
  echo "$CREATE_OUT"
  KV_ID=$(printf '%s' "$CREATE_OUT" | parse_kv_id_from_text)
fi

if [[ -z "$KV_ID" ]]; then
  KV_ID="$(resolve_kv_id)"
fi

if [[ -z "$KV_ID" ]]; then
  echo "::error::Nepodařilo se získat KV namespace ID pro rate limit."
  exit 1
fi

sed -i "s/$PLACEHOLDER/$KV_ID/g" wrangler.toml

cp subscribe.js public/_worker.js

printf '%s' "$ECOMAIL_API_KEY" | npx wrangler@4 pages secret put ECOMAIL_API_KEY --project-name="$PROJECT"
if [[ -n "${ECOMAIL_FROM_EMAIL:-}" ]]; then
  printf '%s' "$ECOMAIL_FROM_EMAIL" | npx wrangler@4 pages secret put ECOMAIL_FROM_EMAIL --project-name="$PROJECT"
  printf '%s' "${NOTIFY_EMAIL:-$ECOMAIL_FROM_EMAIL}" | npx wrangler@4 pages secret put NOTIFY_EMAIL --project-name="$PROJECT"
fi

set +e
DEPLOY_OUTPUT=$(npx wrangler@4 pages deploy public --project-name="$PROJECT" --branch=main 2>&1)
DEPLOY_STATUS=$?
set -e
echo "$DEPLOY_OUTPUT"

URL="https://${PROJECT}.pages.dev"

if [[ "$DEPLOY_STATUS" -ne 0 ]]; then
  write_output ""
  echo "::error::Subscribe API deploy selhal (exit $DEPLOY_STATUS)."
  exit 1
fi

echo "Subscribe API URL: $URL"
write_output "$URL"

if [[ "$GITHUB_OUTPUT_MODE" != "1" ]]; then
  echo ""
  echo "→ URL API odběru: $URL"
  echo "→ Ulož do GitHub Secret SVEJK_SUBSCRIBE_API_URL a spusť deploy webu."
fi

if ! curl -4 -sfI "$URL" >/dev/null 2>&1; then
  echo "::warning::Pages deploy hotov, ale HTTPS ještě neodpovídá — zkus za chvíli: curl -I $URL"
fi
