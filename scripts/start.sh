#!/bin/sh
set -eu

offline="${OFFLINE:-}"
if [ -z "$offline" ] && [ -f .env ]; then
  offline="$(sed -n 's/^[[:space:]]*OFFLINE[[:space:]]*=[[:space:]]*//p' .env | tail -n 1 | tr -d '\r\"' | tr '[:upper:]' '[:lower:]')"
fi

if [ "$offline" = "true" ]; then
  echo "Starting Literae in offline mode (frontend only)."
  docker compose stop api database >/dev/null 2>&1 || true
  exec docker compose up --build --no-deps frontend
fi

echo "Starting the complete Literae stack."
exec docker compose up --build -d
