#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

COMPOSE_FILE="docker-compose.prod.yml"

if [[ ! -f .env.production ]]; then
  echo "ERROR: /opt/crm-dv/.env.production does not exist."
  exit 1
fi

echo "Validating production Compose configuration..."
docker compose -f "$COMPOSE_FILE" config -q

echo "Building and starting production services..."
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans

echo "Waiting for backend healthcheck..."
BACKEND_ID="$(docker compose -f "$COMPOSE_FILE" ps -q backend)"

if [[ -z "$BACKEND_ID" ]]; then
  echo "ERROR: backend container was not created."
  docker compose -f "$COMPOSE_FILE" ps
  exit 1
fi

for attempt in $(seq 1 18); do
  STATUS="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$BACKEND_ID")"

  if [[ "$STATUS" == "healthy" ]]; then
    echo "Backend is healthy."
    docker compose -f "$COMPOSE_FILE" ps
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
  fi

  if [[ "$STATUS" == "unhealthy" ]]; then
    echo "ERROR: backend healthcheck failed."
    docker compose -f "$COMPOSE_FILE" logs --tail=120 backend
    exit 1
  fi

  echo "Backend status: $STATUS (attempt $attempt/18)"
  sleep 5
done

echo "ERROR: backend did not become healthy in time."
docker compose -f "$COMPOSE_FILE" logs --tail=120 backend
exit 1
