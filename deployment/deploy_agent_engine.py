"""Deploys the Aerospace Quality & Reliability Intelligence agent to Vertex
AI Agent Engine with Agent Identity (3-legged OAuth) enabled, following the
Python SDK deployment pattern in
https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#python-sdk-deployment

Run with (from the repo root, so the `app` package resolves):
    uv run python -m deployment.deploy_agent_engine
"""

from __future__ import annotations

import os

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

from app.agent import app as adk_app

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-west1")


def main() -> None:
    # v1beta1 is required for Agent Identity support, per the 3LO deployment
    # guide.
    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )

    agent_engine_app = AdkApp(agent=adk_app)

    remote_app = client.agent_engines.create(
        agent=agent_engine_app,
        config={
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "requirements": [
                "google-cloud-aiplatform[agent_engines,adk]",
                "google-adk[agent-identity,mcp,a2a]>=2.7.1",
                "a2a-sdk>=0.2.0",
                "httpx>=0.27.0",
            ],
            "display_name": "Aerospace Quality & Reliability Intelligence",
        },
    )

    print("Deployed reasoning engine resource name:")
    print(remote_app.resource_name)
    print()
    print("Next steps:")
    print("1. Extract the numeric ENGINE_ID from the resource name above.")
    print("2. Re-run `ENGINE_ID=<id> uv run python -m deployment.setup_auth_provider`")
    print("   so the deployed agent is granted roles/agentidentity.user on the")
    print("   BigQuery 3-legged OAuth auth provider.")
    print("3. Register the agent's A2A endpoint with Gemini Enterprise via")
    print("   `uv run python -m deployment.register_gemini_enterprise` (Cloud Run")
    print("   deployments) or the Gemini Enterprise Agent Registry UI for")
    print("   Agent Engine-hosted agents.")


if __name__ == "__main__":
    main()
