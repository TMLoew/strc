#!/usr/bin/env bash
set -euo pipefail

mkdir -p output/logs

poetry run python -m backend.app.main > output/logs/backend.log 2>&1 &
backend_pid=$!

cleanup() {
  kill "$backend_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

npm --prefix frontend run dev
