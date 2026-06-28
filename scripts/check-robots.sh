#!/usr/bin/env bash
# Ověří, že produkční robots.txt nemá konflikt Cloudflare Managed content vs. Allow pro AI boty.
set -euo pipefail

URL="${1:-https://poslusnehlasim.cz/robots.txt}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== $URL ==="
BODY="$(curl -sS --max-time 20 "$URL")"
echo "$BODY"

echo
echo "=== Kontrola robots.txt ==="

errors=0

if echo "$BODY" | grep -q "BEGIN Cloudflare Managed content"; then
  echo "CHYBA  Cloudflare Managed robots.txt je zapnutý (edge předřazuje Disallow pro AI boty)."
  echo "       Vypni: Cloudflare → AI Crawl Control → Managed robots.txt → Off"
  echo "       Viz ${REPO_ROOT}/infra/cloudflare/README.md §8"
  errors=$((errors + 1))
fi

for bot in GPTBot ClaudeBot Google-Extended PerplexityBot Applebot-Extended; do
  if echo "$BODY" | awk -v bot="$bot" '
    $0 ~ "^User-agent: " bot "$" { in_block=1; next }
    in_block && /^User-agent:/ { in_block=0 }
    in_block && /^Disallow: \// { found=1; exit }
    END { exit !found }
  '; then
    echo "CHYBA  User-agent: $bot má Disallow: / (blokuje crawl)"
    errors=$((errors + 1))
  fi
done

if ! echo "$BODY" | grep -q "Content-Signal: search=yes,ai-train=no"; then
  echo "VAROVÁNÍ  Chybí Content-Signal: search=yes,ai-train=no"
fi

if ! echo "$BODY" | grep -q "Sitemap:.*sitemap.xml"; then
  echo "CHYBA  Chybí odkaz na sitemap.xml"
  errors=$((errors + 1))
fi

if [ "$errors" -gt 0 ]; then
  exit 1
fi

echo "OK  robots.txt bez konfliktu Cloudflare vs. Allow"
