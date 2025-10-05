#!/usr/bin/env bash
# Runs on the server from the release directory. Called by deploy.sh.
set -euo pipefail

secret() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-40}"; }

# Values generated once and kept across releases.
if [ ! -f .env.server ]; then
  umask 077
  {
    echo "SECRET_KEY=$(secret 48)"
    echo "POSTGRES_PASSWORD=$(secret 32)"
    echo "OWNER_PASSWORD=$(secret 20)"
  } > .env.server
fi

# Compose reads .env for ${VARS}: generated values first, then the shipped ones.
umask 077
cat .env.server .env.production > .env
rm -f .env.production

COMPOSE="docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml"
$COMPOSE up -d --build --remove-orphans

# The API container migrates and seeds on start; wait until it answers.
for _ in $(seq 1 90); do
  if $COMPOSE exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; then
    break
  fi
  sleep 5
done

# Send-only Telegram setups link the owner's site to a chat directly.
set -a; . ./.env; set +a
if [ -n "${TELEGRAM_CHAT_ID:-}" ] && [ -n "${OWNER_SITE_KEY:-}" ]; then
  $COMPOSE exec -T api python -m app.cli link-telegram "$OWNER_SITE_KEY" "$TELEGRAM_CHAT_ID" --title "${TELEGRAM_CHAT_TITLE:-Managers}"
fi

$COMPOSE ps
