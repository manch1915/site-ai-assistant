#!/usr/bin/env bash
# Ships the committed tree to a server and (re)starts the stack, in one SSH connection.
#
#   bash deploy/deploy.sh narcisvps [/opt/relay]
#
# deploy/.env.production (not in git) carries the values you set yourself: PUBLIC_URL,
# LLM key, Telegram token and chat. Database password, secret key and the owner's
# password are generated on the server on first run and never leave it.
set -euo pipefail

HOST="${1:?usage: deploy.sh <ssh-host> [remote-dir]}"
DIR="${2:-/opt/relay}"
ENV_FILE="deploy/.env.production"

cd "$(dirname "$0")/.."
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE (see .env.example)" >&2; exit 1; }

# The release carries secrets, so it is unpacked into a directory only root can read.
git archive --format=tar --add-file="$ENV_FILE" HEAD \
  | ssh "$HOST" "umask 077 && mkdir -p '$DIR' && chmod 700 '$DIR' \
      && tar -x --no-same-permissions -C '$DIR' && cd '$DIR' && bash deploy/remote.sh"
