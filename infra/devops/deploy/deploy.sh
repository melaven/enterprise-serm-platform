#!/usr/bin/env bash
# Запускается на сервере пользователем deploy (из CI). Идемпотентен, откатывается при провале healthcheck.
set -euo pipefail
cd /opt/tenable
NEW_IMAGE="${1:?usage: deploy.sh <image@digest>}"
PREV_IMAGE="$(grep -E '^IMAGE=' .deploy_state 2>/dev/null | cut -d= -f2- || true)"

export IMAGE="$NEW_IMAGE"
docker compose --env-file .env -f docker-compose.prod.yml pull api
docker compose --env-file .env -f docker-compose.prod.yml up -d --remove-orphans --wait --wait-timeout 120 \
  || { echo "::error::deploy failed"; 
       if [[ -n "$PREV_IMAGE" ]]; then
         echo "rollback -> $PREV_IMAGE"; export IMAGE="$PREV_IMAGE"
         docker compose --env-file .env -f docker-compose.prod.yml up -d --wait --wait-timeout 120
       fi; exit 1; }

echo "IMAGE=$NEW_IMAGE" > .deploy_state
docker image prune -f --filter "until=168h" >/dev/null
echo "deployed $NEW_IMAGE"
