#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-models}"
DETECTOR_MODEL_PATH="${DETECTOR_MODEL_PATH:-models/best.pt}"
MODEL_DOWNLOAD_URL="${MODEL_DOWNLOAD_URL:-}"

mkdir -p "$MODEL_DIR"

if [ -f "$DETECTOR_MODEL_PATH" ]; then
  echo "Detector model already exists: $DETECTOR_MODEL_PATH"
  exit 0
fi

if [ -z "$MODEL_DOWNLOAD_URL" ]; then
  echo "MODEL_DOWNLOAD_URL is empty."
  echo "Copy your detector model to: $DETECTOR_MODEL_PATH"
  echo "Or set MODEL_DOWNLOAD_URL in .env and run this script again."
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  curl -L "$MODEL_DOWNLOAD_URL" -o "$DETECTOR_MODEL_PATH"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$DETECTOR_MODEL_PATH" "$MODEL_DOWNLOAD_URL"
else
  echo "curl or wget is required."
  exit 1
fi

echo "Model downloaded to: $DETECTOR_MODEL_PATH"
