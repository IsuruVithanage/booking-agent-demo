#!/usr/bin/env bash
# Calls the deployed isolation-verification agent's /verify endpoint and
# pretty-prints the results. Requires AMP_AGENT_API_KEY to be set to a
# valid API key for the isolated-agent deployment.
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://default-default.am-gateway.localhost:19080/isolated-agent-isolated-agent-endpoint}"

if [[ -z "${AMP_AGENT_API_KEY:-}" ]]; then
  echo "Set AMP_AGENT_API_KEY to a valid API key for the isolated-agent deployment." >&2
  echo "  Issue one with:" >&2
  echo "  amctl api -X POST /orgs/default/projects/default/agents/isolated-agent/environments/default/api-keys -f name=probe-run" >&2
  exit 1
fi

curl -sf "${GATEWAY_URL}/verify" -H "X-API-Key: ${AMP_AGENT_API_KEY}" | jq .
