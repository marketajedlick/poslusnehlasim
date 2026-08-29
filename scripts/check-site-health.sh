#!/usr/bin/env bash
# Dostupnost homepage + stav TLS certifikátu GitHub Pages (cron v site-health.yml).
set -euo pipefail

URL="${1:-https://poslusnehlasim.cz/}"
REPO="${GITHUB_REPOSITORY:-marketajedlick/poslusnehlasim}"
MIN_CERT_DAYS="${MIN_CERT_DAYS:-7}"

echo "=== Homepage: $URL ==="
status="$(curl -sS -o /dev/null -w '%{http_code}' -L --max-time 30 "$URL")"
if [ "$status" != "200" ]; then
  echo "::error::Homepage vrátila HTTP $status (očekáváno 200)"
  exit 1
fi
echo "OK  HTTP 200"

echo
echo "=== GitHub Pages certifikát ($REPO) ==="
if ! command -v gh >/dev/null 2>&1; then
  echo "::error::gh CLI není k dispozici"
  exit 1
fi

cert_json="$(gh api "repos/$REPO/pages" --jq '.https_certificate')"
state="$(echo "$cert_json" | jq -r '.state // empty')"
expires="$(echo "$cert_json" | jq -r '.expires_at // empty')"
desc="$(echo "$cert_json" | jq -r '.description // empty')"

echo "state=$state expires_at=$expires"
[ -n "$desc" ] && echo "  $desc"

if [ "$state" != "approved" ]; then
  echo "::error::Certifikát není approved (state=$state). Zkontroluj Settings → Pages a Cloudflare DNS."
  exit 1
fi
echo "OK  state approved"

if [ -z "$expires" ]; then
  echo "::error::Chybí expires_at v GitHub Pages API"
  exit 1
fi

days_left="$(python3 - "$expires" <<'PY'
from datetime import date, datetime, timezone
import sys

expires = date.fromisoformat(sys.argv[1])
today = datetime.now(timezone.utc).date()
print((expires - today).days)
PY
)"

echo "OK  platnost ještě $days_left dní (do $expires)"

if [ "$days_left" -lt 0 ]; then
  echo "::error::Certifikát expiroval $expires"
  exit 1
fi

if [ "$days_left" -lt "$MIN_CERT_DAYS" ]; then
  echo "::error::Certifikát expiruje za $days_left dní (< $MIN_CERT_DAYS). Obnova selhala nebo neproběhla — viz infra/cloudflare/README.md"
  exit 1
fi

echo
echo "Web i certifikát v pořádku."
