"""Registers this agent's A2A endpoint with Gemini Enterprise so it can be
shared with employees and rendered through the built-in A2UI renderer, per
https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
("Register it as an A2A endpoint...").

Cross-platform (Windows/macOS/Linux) equivalent of the previous
`register_gemini_enterprise.sh`.

Usage:
    PROJECT_ID=my-project LOCATION=global AGENT_PUBLIC_URL=https://... \
    ASSISTANT_ID=<assistant-id> \
    uv run python -m deployment.register_gemini_enterprise
"""

from __future__ import annotations

import os
import sys

import httpx

from ._gcloud import access_token

DISCOVERY_ENGINE_BASE = "https://discoveryengine.googleapis.com/v1alpha"


def _require_env(name: str, hint: str = "") -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Set the {name} environment variable before running this script.{hint}")
    return value


def main() -> None:
    project_id = _require_env("PROJECT_ID")
    location = os.environ.get("LOCATION", "global")
    agent_public_url = _require_env(
        "AGENT_PUBLIC_URL", " (the deployed Cloud Run / GKE URL)"
    )
    agent_display_name = os.environ.get(
        "AGENT_DISPLAY_NAME", "Aerospace Quality & Reliability Intelligence"
    )
    assistant_id = _require_env(
        "ASSISTANT_ID", " (the target Gemini Enterprise assistant id)"
    )

    agent_card_uri = f"{agent_public_url}/.well-known/agent-card.json"
    print(f"==> Registering A2A agent card at {agent_card_uri}")

    url = (
        f"{DISCOVERY_ENGINE_BASE}/projects/{project_id}/locations/{location}"
        f"/collections/default_collection/engines/{assistant_id}"
        f"/assistants/default_assistant/agents"
    )
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token()}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": project_id,
            },
            json={
                "displayName": agent_display_name,
                "a2aAgentDefinition": {"agentCardUri": agent_card_uri},
            },
        )
        print(resp.status_code, resp.text[:2000])

    print(
        "\nThen, in the Gemini Enterprise console, an administrator shares the "
        "agent with the intended employees/groups from the agent catalog, "
        "exactly like any other Gemini Enterprise agent, per the 'Share the "
        "agent' step in "
        "https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration"
    )
    print(
        "\nNOTE: the exact Discovery Engine 'agents' sub-resource path/version "
        "can change between Gemini Enterprise releases -- verify the current "
        "path/permissions in the Google Cloud console under Gemini Enterprise "
        "> Agents > Register agent before relying on this script in production."
    )


if __name__ == "__main__":
    main()
