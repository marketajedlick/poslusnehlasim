#!/usr/bin/env bash
# Ověří dlouhý Cache-Control u statických assetů (PageSpeed cache lifetimes).
set -euo pipefail

URL="${1:-https://poslusnehlasim.cz/static/fonts.css}"
MIN_MAX_AGE="${MIN_MAX_AGE:-2592000}" # 30 dní

echo "=== $URL ==="
HEADERS="$(curl -sSI "$URL" | tr -d '\r')"
echo "$HEADERS" | grep -iE '^(HTTP/|cache-control:|age:|cf-cache-status:)' || true

cc="$(echo "$HEADERS" | grep -i '^cache-control:' | head -1 || true)"
if [ -z "$cc" ]; then
  echo "CHYBÍ  cache-control"
  echo "Viz infra/cloudflare/README.md (Transform Rule Static cache)."
  exit 1
fi

max_age="$(echo "$cc" | grep -oiE 'max-age=[0-9]+' | head -1 | cut -d= -f2 || true)"
if [ -z "$max_age" ]; then
  echo "CHYBÍ  max-age v: $cc"
  exit 1
fi

if [ "$max_age" -lt "$MIN_MAX_AGE" ]; then
  echo "SLABÉ  cache-control max-age=$max_age (chci ≥ $MIN_MAX_AGE)"
  echo "GitHub Pages default je 14400 (4 h). Přidej Cloudflare Transform Rule."
  echo "Viz infra/cloudflare/README.md"
  exit 1
fi

echo "OK  cache-control max-age=$max_age"
