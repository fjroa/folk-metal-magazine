#!/usr/bin/env bash
# Wrapper: discografía incremental con credenciales del .env
set -euo pipefail
ENV_FILE="$HOME/.hermes/.env"
export SPOTIFY_CLIENT_ID="$(grep '^SPOTIFY_CLIENT_ID=' "$ENV_FILE" | cut -d= -f2)"
export SPOTIFY_CLIENT_SECRET="$(grep '^SPOTIFY_CLIENT_SECRET=' "$ENV_FILE" | cut -d= -f2)"
cd "$HOME/github/folk-metal-magazine"
exec python3 scripts/band_discography_batch.py "$@"
