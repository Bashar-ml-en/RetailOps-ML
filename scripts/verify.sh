#!/usr/bin/env sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${PYTHON_BIN:-python}

(
  cd "$repository_root/backend"
  "$python_bin" -m pytest --basetemp "$repository_root/.pytest-tmp" -q
)

(
  cd "$repository_root/frontend"
  pnpm install --frozen-lockfile
  pnpm run verify
)
