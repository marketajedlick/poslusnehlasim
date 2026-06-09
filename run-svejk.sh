#!/usr/bin/env bash
# Spusti svejk.py spravnym Pythonem 3.12 (conda env 'svejk' nebo .venv).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ -f "$ROOT/secrets.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/secrets.env"
  set +a
fi

find_python() {
  local candidates=(
    "$HOME/anaconda3/envs/svejk/bin/python"
    "$HOME/miniconda3/envs/svejk/bin/python"
    "$ROOT/.venv/bin/python"
  )
  for py in "${candidates[@]}"; do
    if [[ -x "$py" ]]; then
      echo "$py"
      return 0
    fi
  done
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return 0
  fi
  return 1
}

PY="$(find_python)" || {
  echo "Nenasel jsem Python 3.12 pro projekt Svejk." >&2
  echo "Vytvor conda env:" >&2
  echo "  conda create -n svejk python=3.12 -y" >&2
  echo "  conda activate svejk" >&2
  echo "  pip install -r requirements-svejk.txt" >&2
  exit 1
}

# conda env bez balicku -> doinstaluj
if ! "$PY" -c "import sqlalchemy" 2>/dev/null; then
  echo "Doinstalovavam zavislosti do $PY ..."
  "$PY" -m pip install -r "$ROOT/requirements-svejk.txt"
fi

exec "$PY" "$ROOT/svejk.py" "$@"
