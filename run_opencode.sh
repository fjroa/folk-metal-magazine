#!/usr/bin/env bash
# Wrapper: carga OPENROUTER_API_KEY desde ~/.hermes/.env y ejecuta opencode.
set -euo pipefail
ENV_FILE="$HOME/.hermes/.env"
if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r k v; do
    [[ "$k" == "OPENROUTER_API_KEY" && -n "$v" ]] && export OPENROUTER_API_KEY="$v"
  done < <(grep -E '^OPENROUTER_API_KEY=' "$ENV_FILE")
fi
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "ERROR: OPENROUTER_API_KEY no encontrada en $ENV_FILE" >&2
  exit 1
fi
cd "$HOME/github/folk-metal-magazine"
exec opencode run --model openrouter/openai/gpt-5.6-luna "$@"
