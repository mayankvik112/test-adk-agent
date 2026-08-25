r"""Creates the 3-legged OAuth (3LO) Agent Identity auth provider that lets
the agent query BigQuery with the *signed-in engineer's own* credentials,
per https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2

Cross-platform (Windows/macOS/Linux) equivalent of the previous
`setup_auth_provider.sh`. Requires the `gcloud` CLI to be installed and
authenticated (`gcloud init`).

Before running this script:
    1. Enable the Agent Identity API:
         gcloud services enable agentidentity.googleapis.com --project=<PROJECT_ID>
    2. Configure the OAuth consent screen (APIs & Services > OAuth consent
       screen) for this project if you have not already.
    3. Create a Web-application OAuth client (APIs & Services > Credentials)
       -- you will register its redirect URI with this script (step 1
       below) BEFORE the auth provider is created, then re-run with the
       resulting OAUTH_CLIENT_ID / OAUTH_CLIENT_SECRET.

Usage:
    PROJECT_ID=my-project LOCATION=us-west1 \
    OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com OAUTH_CLIENT_SECRET=yyy \
    ENGINE_ID=<deployed reasoning engine numeric id>  \  # optional, step 3b
    uv run python -m deployment.setup_auth_provider
"""

from __future__ import annotations

import os
import sys

from ._gcloud import current_account, project_number, run_gcloud


def _require_env(name: str, hint: str = "") -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Set the {name} environment variable before running this script.{hint}")
    return value


def main() -> None:
    project_id = _require_env("PROJECT_ID")
    location = os.environ.get("LOCATION", "us-west1")
    auth_provider_name = os.environ.get(
        "AUTH_PROVIDER_NAME", "aerospace-bigquery-3lo-authprovider"
    )
    oauth_client_id = _require_env(
        "OAUTH_CLIENT_ID", " (from the Web-application OAuth client)"
    )
    oauth_client_secret = _require_env(
        "OAUTH_CLIENT_SECRET", " (from the same OAuth client)"
    )
    authorization_url = os.environ.get(
        "AUTHORIZATION_URL", "https://accounts.google.com/o/oauth2/v2/auth"
    )
    token_url = os.environ.get("TOKEN_URL", "https://oauth2.googleapis.com/token")
    engine_id = os.environ.get("ENGINE_ID")

    callback_url = (
        "https://agentidentitycredentials.googleapis.com/v1/projects/"
        f"{project_id}/locations/{location}/authProviders/{auth_provider_name}"
        "/oauthcallback"
    )

    print("==> [1/3] Redirect URI to register on the OAuth client BEFORE creating "
          "the auth provider:")
    print(f"    {callback_url}")
    print("    (APIs & Services > Credentials > <your Web-application client> "
          "> Authorized redirect URIs)")
    input("Press enter once the redirect URI is registered on the OAuth client... ")

    print(f"\n==> [2/3] Creating 3-legged OAuth auth provider '{auth_provider_name}'")
    run_gcloud(
        [
            "agent-identity", "auth-providers", "create", auth_provider_name,
            f"--project={project_id}",
            f"--location={location}",
            f"--three-legged-oauth-client-id={oauth_client_id}",
            f"--three-legged-oauth-client-secret={oauth_client_secret}",
            f"--three-legged-oauth-authorization-url={authorization_url}",
            f"--three-legged-oauth-token-url={token_url}",
        ],
        capture=False,
    )

    print("\n==> Verifying auth provider is ENABLED")
    run_gcloud(
        ["agent-identity", "auth-providers", "list",
         f"--project={project_id}", f"--location={location}"],
        capture=False,
    )

    print("\n==> [3/3] Granting Agent Identity User access")
    account = current_account()
    print(f"    a) Grant access to your own account ({account}) for local "
          "'adk web' / 'uv run adk web app' testing:")
    run_gcloud(
        [
            "agent-identity", "auth-providers", "add-iam-policy-binding",
            auth_provider_name,
            f"--project={project_id}",
            f"--location={location}",
            "--role=roles/agentidentity.user",
            f"--member=user:{account}",
        ],
        capture=False,
    )

    if engine_id:
        print(f"    b) Granting access to the deployed reasoning engine "
              f"(ENGINE_ID={engine_id})")
        number = project_number(project_id)
        member = (
            "principal://agents.global.org-system.id.goog/resources/aiplatform/"
            f"projects/{number}/locations/{location}/reasoningEngines/{engine_id}"
        )
        run_gcloud(
            [
                "agent-identity", "auth-providers", "add-iam-policy-binding",
                auth_provider_name,
                f"--project={project_id}",
                f"--location={location}",
                "--role=roles/agentidentity.user",
                f"--member={member}",
            ],
            capture=False,
        )
    else:
        print(
            "    b) Skipped: set ENGINE_ID after "
            "`uv run python -m deployment.deploy_agent_engine` and re-run this "
            "script to grant the deployed agent access, per "
            "https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#google-cloud-cli"
        )

    print(
        f"\nSet BIGQUERY_AUTH_PROVIDER_NAME={auth_provider_name} in your .env to "
        "match app/auth/auth_provider.py"
    )


if __name__ == "__main__":
    main()
