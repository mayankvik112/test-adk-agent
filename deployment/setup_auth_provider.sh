#!/usr/bin/env bash
# Creates the 3-legged OAuth (3LO) Agent Identity auth provider that lets
# the agent query BigQuery with the *signed-in engineer's own* credentials,
# per https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2
#
# Usage:
#   PROJECT_ID=my-project LOCATION=us-west1 \
#   OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com OAUTH_CLIENT_SECRET=yyy \
#   ENGINE_ID=<deployed reasoning engine numeric id> \
#   ./deployment/setup_auth_provider.sh
#
# Before running this script:
#   1. Enable the Agent Identity API:
#        gcloud services enable agentidentity.googleapis.com --project="$PROJECT_ID"
#   2. Configure the OAuth consent screen (APIs & Services > OAuth consent
#      screen) for this project if you have not already.
#   3. Create a Web-application OAuth client (APIs & Services > Credentials)
#      whose "Authorized redirect URIs" includes the callback URL this
#      script prints in step 1 below -- you must add it to the OAuth client
#      BEFORE creating the auth provider, then re-run with the resulting
#      OAUTH_CLIENT_ID / OAUTH_CLIENT_SECRET.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
LOCATION="${LOCATION:-us-west1}"
AUTH_PROVIDER_NAME="${AUTH_PROVIDER_NAME:-aerospace-bigquery-3lo-authprovider}"
OAUTH_CLIENT_ID="${OAUTH_CLIENT_ID:?Set OAUTH_CLIENT_ID from the Web-application OAuth client}"
OAUTH_CLIENT_SECRET="${OAUTH_CLIENT_SECRET:?Set OAUTH_CLIENT_SECRET from the same OAuth client}"
AUTHORIZATION_URL="${AUTHORIZATION_URL:-https://accounts.google.com/o/oauth2/v2/auth}"
TOKEN_URL="${TOKEN_URL:-https://oauth2.googleapis.com/token}"

CALLBACK_URL="https://agentidentitycredentials.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/authProviders/${AUTH_PROVIDER_NAME}/oauthcallback"

echo "==> [1/3] Redirect URI to register on the OAuth client BEFORE creating the auth provider:"
echo "    ${CALLBACK_URL}"
echo "    (APIs & Services > Credentials > <your Web-application client> > Authorized redirect URIs)"
read -rp "Press enter once the redirect URI is registered on the OAuth client... "

echo "==> [2/3] Creating 3-legged OAuth auth provider '${AUTH_PROVIDER_NAME}'"
gcloud agent-identity auth-providers create "${AUTH_PROVIDER_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}" \
  --three-legged-oauth-client-id="${OAUTH_CLIENT_ID}" \
  --three-legged-oauth-client-secret="${OAUTH_CLIENT_SECRET}" \
  --three-legged-oauth-authorization-url="${AUTHORIZATION_URL}" \
  --three-legged-oauth-token-url="${TOKEN_URL}"

echo "==> Verifying auth provider is ENABLED"
gcloud agent-identity auth-providers list \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}"

echo "==> [3/3] Granting Agent Identity User access"
echo "    a) Grant access to your own account for local 'adk web' testing:"
gcloud agent-identity auth-providers add-iam-policy-binding "${AUTH_PROVIDER_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}" \
  --role="roles/agentidentity.user" \
  --member="user:$(gcloud config get-value account)"

if [[ -n "${ENGINE_ID:-}" ]]; then
  echo "    b) Granting access to the deployed reasoning engine (ENGINE_ID=${ENGINE_ID})"
  gcloud agent-identity auth-providers add-iam-policy-binding "${AUTH_PROVIDER_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --role="roles/agentidentity.user" \
    --member="principal://agents.global.org-system.id.goog/resources/aiplatform/projects/$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')/locations/${LOCATION}/reasoningEngines/${ENGINE_ID}"
else
  echo "    b) Skipped: set ENGINE_ID after 'make deploy-agent-engine' and re-run this script to"
  echo "       grant the deployed agent access, per"
  echo "       https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#google-cloud-cli"
fi

echo
echo "Set BIGQUERY_AUTH_PROVIDER_NAME=${AUTH_PROVIDER_NAME} in your .env to match app/auth/auth_provider.py"
