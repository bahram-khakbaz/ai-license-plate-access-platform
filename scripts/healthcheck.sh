#!/usr/bin/env bash
set -euo pipefail

URL="${URL:-http://localhost:5000/status}"

if curl -fsS "$URL" >/dev/null; then
  echo "OK: $URL"
else
  echo "FAILED: $URL"
  exit 1
fi
