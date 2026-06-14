#!/usr/bin/env bash
# Ověří bezpečnostní hlavičky na produkčním webu.
set -euo pipefail

URL="${1:-https://poslusnehlasim.cz/}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXPECTED_FILE="$REPO_ROOT/infra/cloudflare/headers.txt"

echo "=== $URL ==="
HEADERS="$(curl -sSI "$URL" | tr -d '\r')"
echo "$HEADERS" | grep -iE '^(HTTP/|server:|via:|cf-|strict-transport|content-security|x-frame|x-content-type|referrer-policy|permissions-policy|cross-origin)' || true

echo
echo "=== Kontrola povinných hlaviček ==="

check_header() {
  local name="$1"
  if echo "$HEADERS" | grep -qi "^${name}:"; then
    echo "OK  $name"
    return 0
  fi
  echo "CHYBÍ  $name"
  return 1
}

missing=0
check_header "strict-transport-security" || missing=$((missing + 1))
check_header "content-security-policy" || missing=$((missing + 1))
check_header "x-frame-options" || missing=$((missing + 1))
check_header "x-content-type-options" || missing=$((missing + 1))
check_header "referrer-policy" || missing=$((missing + 1))

if echo "$HEADERS" | grep -qi '^server: GitHub.com'; then
  echo
  echo "POZNÁMKA: Odpověď jde přímo z GitHub Pages (server: GitHub.com)."
  echo "         Hlavičky přidá až Cloudflare proxy + Transform Rules."
  echo "         Viz infra/cloudflare/README.md"
fi

if echo "$HEADERS" | grep -qi '^cf-ray:'; then
  echo
  echo "Cloudflare proxy aktivní (cf-ray v odpovědi)."
fi

if [ "$missing" -gt 0 ]; then
  echo
  echo "Chybí $missing hlaviček. Očekávané hodnoty: $EXPECTED_FILE"
  exit 1
fi

echo
echo "Všechny kontrolované hlavičky jsou přítomné."
