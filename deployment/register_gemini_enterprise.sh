#!/usr/bin/env bash
# Registers this agent's A2A endpoint with Gemini Enterprise so it can be
# shared with employees and rendered through the built-in A2UI renderer, per
# https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
# ("Register it as an A2A endpoint... the reference repository command is
# `make register-gemini-enterprise`").
#
# Usage:
#   PROJECT_ID=my-project LOCATION=global AGENT_PUBLIC_URL=https://... \
#   ./deployment/register_gemini_enterprise.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
LOCATION="${LOCATION:-global}"
AGENT_PUBLIC_URL="${AGENT_PUBLIC_URL:?Set AGENT_PUBLIC_URL to the deployed Cloud Run / GKE URL}"
AGENT_DISPLAY_NAME="${AGENT_DISPLAY_NAME:-Aerospace Quality & Reliability Intelligence}"
ASSISTANT_ID="${ASSISTANT_ID:?Set ASSISTANT_ID to the target Gemini Enterprise assistant id}"

echo "==> Registering A2A agent card at ${AGENT_PUBLIC_URL}/.well-known/agent-card.json"
curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/${LOCATION}/collections/default_collection/engines/${ASSISTANT_ID}/assistants/default_assistant/agents" \
  -d "{
    \"displayName\": \"${AGENT_DISPLAY_NAME}\",
    \"a2aAgentDefinition\": {
      \"agentCardUri\": \"${AGENT_PUBLIC_URL}/.well-known/agent-card.json\"
    }
  }"

echo
echo "Then, in the Gemini Enterprise console, an administrator shares the agent"
echo "with the intended employees/groups from the agent catalog, exactly like any"
echo "other Gemini Enterprise agent, per the 'Share the agent' step in"
echo "https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration"
echo
echo "NOTE: the exact Discovery Engine 'agents' sub-resource path/version can change"
echo "between Gemini Enterprise releases -- verify the current path/permissions in the"
echo "Google Cloud console under Gemini Enterprise > Agents > Register agent before"
echo "relying on this script in production."
