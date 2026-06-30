#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai-license-plate-access-platform}"
REPO_URL="${REPO_URL:-https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Please install Docker first."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is not installed. Please install git first."
  exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
mkdir -p data uploads exports logs backups

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Edit it before production use."
fi

docker compose up -d --build

echo "Deployment finished. Open the configured host and port in your browser."
