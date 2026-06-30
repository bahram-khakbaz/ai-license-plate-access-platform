#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$BACKUP_DIR/$STAMP"

mkdir -p "$OUT_DIR"

if [ -f .env ]; then
  cp .env "$OUT_DIR/env.backup"
fi

if [ -f data/app.db ]; then
  cp data/app.db "$OUT_DIR/app.db"
fi

if [ -f data/traffic.db ]; then
  cp data/traffic.db "$OUT_DIR/traffic.db"
fi

if [ -d exports ]; then
  tar -czf "$OUT_DIR/exports.tar.gz" exports
fi

if [ -d uploads ]; then
  tar -czf "$OUT_DIR/uploads.tar.gz" uploads
fi

echo "Backup created at: $OUT_DIR"
