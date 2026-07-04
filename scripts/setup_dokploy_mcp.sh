#!/usr/bin/env bash
# setup_dokploy_mcp.sh — config-as-code for the Dokploy MCP integration (Stream A).
#
# Registers the @dokploy/mcp server GLOBALLY (Claude Code user scope) so every
# Claude Code session can do Dokploy ops via MCP tools instead of ad-hoc
# SSH/curl. Idempotent: safe to re-run (re-adds the server).
#
# The Dokploy credentials are NOT stored here. They live in a gitignored env
# file that the operator sources before launching Claude Code, so the MCP's
# ${DOKPLOY_URL} / ${DOKPLOY_API_KEY} expand at tool-spawn time.
set -euo pipefail

CREDS="${HOME}/.config/daslab/dokploy-mcp.env"

# Deploy-focused tag filter: 508 tools -> ~199 (application/compose/deployment/
# docker/db/domain/cert/backup/server/registry). Redact secrets from responses.
TAGS="project,application,compose,deployment,docker,domain,certificate,postgres,mysql,mongo,redis,backup,server,registry"

echo "==> Registering dokploy MCP (user scope, all agents)…"
claude mcp remove dokploy -s user >/dev/null 2>&1 || true
claude mcp add dokploy --scope user \
  -e 'DOKPLOY_URL=${DOKPLOY_URL}' \
  -e 'DOKPLOY_API_KEY=${DOKPLOY_API_KEY}' \
  -e "DOKPLOY_ENABLED_TAGS=${TAGS}" \
  -e 'DOKPLOY_REDACT_ENV=true' \
  -- npx -y @dokploy/mcp@latest

echo "==> Ensuring creds env file…"
mkdir -p "$(dirname "$CREDS")"
if [ ! -f "$CREDS" ]; then
  cat > "$CREDS" <<'ENV'
# Dokploy MCP credentials — fill these in, then source this file before Claude Code.
# Get an API token in Dokploy: Settings -> API/Tokens.
export DOKPLOY_URL="https://your-dokploy-server.example.com"
export DOKPLOY_API_KEY="paste-dokploy-api-token-here"
ENV
  chmod 600 "$CREDS"
  echo "    created template: $CREDS  (chmod 600) — EDIT IT with real creds."
else
  echo "    exists: $CREDS"
fi

echo
echo "==> Done. Next steps (operator):"
echo "   1. Edit $CREDS with the real DOKPLOY_URL + DOKPLOY_API_KEY."
echo "   2. Source it before launching Claude Code so MCP tools inherit the creds:"
echo "        set -a; source $CREDS; set +a; claude"
echo "   3. Verify:  claude mcp get dokploy   (Status: ✓ Connected)"
echo "   4. An agent can now call dokploy MCP tools (application-create, deploy, etc.)."
