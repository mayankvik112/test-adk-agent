"""3-legged OAuth (3LO) wiring for the BigQuery connector.

This module implements the ADK-side half of the flow documented at
https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2 :

  1. An Agent Identity "auth provider" resource of type `OAuth (3 legged)`
     is created out-of-band (see ../deployment/setup_auth_provider.py) and
     points at Google's OAuth endpoints with a Web-application OAuth client
     registered for the callback URL
     `https://agentidentitycredentials.googleapis.com/v1/projects/<PROJECT_ID>/
     locations/<LOCATION>/authProviders/<AUTH_PROVIDER_NAME>/oauthcallback`.
  2. This module registers the GCP auth provider with ADK's
     `CredentialManager`, builds a `GcpAuthProviderScheme` that references
     that auth provider resource + the BigQuery OAuth scope, and wraps it in
     an `AuthConfig` that tools can attach to.
  3. When a live BigQuery call is needed and the current end user has not
     yet granted consent, ADK automatically emits an `adk_request_credential`
     function call; the Gemini Enterprise / custom frontend handles the
     consent redirect and resumes the conversation once the user has
     authorized access. ADK then injects the resulting user-scoped OAuth
     token into the tool call for us (see `bigquery_live_query.py`).

Because the token that comes back belongs to the signed-in end user (not a
shared service account), BigQuery's own IAM / row-level and column-level
security rules apply exactly as they would if the engineer ran the query
themselves in the BigQuery console.
"""

from __future__ import annotations

import os

from google.adk.auth.auth_tool import AuthConfig
from google.adk.integrations.agent_identity import (
    GcpAuthProvider,
    GcpAuthProviderScheme,
)
from google.adk.auth.credential_manager import CredentialManager

# Name of the Agent Identity auth provider resource created by
# deployment/setup_auth_provider.py. Must be lowercase letters/digits/hyphens,
# start with a letter, and not end with a hyphen (per the 3LO setup docs).
AUTH_PROVIDER_NAME = os.environ.get(
    "BIGQUERY_AUTH_PROVIDER_NAME", "aerospace-bigquery-3lo-authprovider"
)

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-west1")

# BigQuery OAuth scope used by the Agent Identity 3LO auth-with-3lo-v2 guide.
BIGQUERY_OAUTH_SCOPE = "https://www.googleapis.com/auth/bigquery"

# Where Gemini Enterprise / the custom frontend resumes the conversation
# after the user grants (or denies) consent. For Gemini Enterprise-hosted
# agents this is handled by the platform's own consent surface; the value
# below is only used for local `adk web` / custom-frontend development, per
# https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#custom-ui-application
CONTINUE_URI = os.environ.get(
    "BIGQUERY_OAUTH_CONTINUE_URI", "http://127.0.0.1:8501/validateUserId"
)

_provider_registered = False


def register_gcp_auth_provider() -> None:
    """Registers the GCP auth provider with ADK's CredentialManager.

    Idempotent — safe to call from multiple modules at import time.
    """
    global _provider_registered
    if _provider_registered:
        return
    CredentialManager.register_auth_provider(GcpAuthProvider())
    _provider_registered = True


def get_bigquery_auth_config() -> AuthConfig:
    """Builds the `AuthConfig` describing the 3-legged OAuth BigQuery grant.

    The resource name follows
    `projects/<PROJECT_ID>/locations/<LOCATION>/authProviders/<AUTH_PROVIDER_NAME>`
    as required by https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#agent-code-implementation-with-adk.
    """
    register_gcp_auth_provider()

    auth_scheme = GcpAuthProviderScheme(
        name=(
            f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}/"
            f"authProviders/{AUTH_PROVIDER_NAME}"
        ),
        scopes=[BIGQUERY_OAUTH_SCOPE],
        continue_uri=CONTINUE_URI,
    )
    return AuthConfig(auth_scheme=auth_scheme)
