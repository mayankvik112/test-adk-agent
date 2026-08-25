"""Uvicorn entry point: serves the Aerospace Quality & Reliability
Intelligence agent as an A2A endpoint that Gemini Enterprise (or the
optional custom Lit shell) can call directly, following the deployment
shape described in
https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
("The A2A endpoint can run on Cloud Run, GKE, or on-premises
infrastructure. Gemini Enterprise handles rendering.").

Run locally:
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

Then register the agent with Gemini Enterprise as an A2A endpoint (see
`deployment/register_gemini_enterprise.sh`), pointing it at this server's
public URL + `/a2a` path.
"""

from __future__ import annotations

import os

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.agent_executor import AerospaceAgentExecutor

AGENT_HOST = os.environ.get("AGENT_PUBLIC_URL", "http://localhost:8080")

agent_card = AgentCard(
    name="Aerospace Quality & Reliability Intelligence",
    description=(
        "Searches and analyzes aircraft defect records (defect_id, "
        "aircraft_model, component_category, severity_level, "
        "defect_description) sourced from a BigQuery-connector-backed "
        "Gemini Enterprise Data Store, with 3-legged-OAuth-authenticated "
        "live BigQuery analytics and native A2UI result surfaces."
    ),
    url=f"{AGENT_HOST}/a2a",
    version="1.0.0",
    default_input_modes=["text", "application/json+a2ui"],
    default_output_modes=["text", "application/json+a2ui"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="search_defects",
            name="Search aircraft defects",
            description=(
                "Free-text / filtered search over the BigQuery-connector-"
                "backed Gemini Enterprise Data Store of aircraft defect "
                "records."
            ),
            tags=["aerospace", "quality", "reliability", "bigquery", "search"],
        ),
        AgentSkill(
            id="query_live_defect_analytics",
            name="Live BigQuery defect analytics",
            description=(
                "Runs read-only, 3-legged-OAuth-authenticated SQL "
                "aggregations directly against the live BigQuery aircraft "
                "defects table, scoped to the signed-in engineer's own "
                "IAM permissions."
            ),
            tags=["aerospace", "bigquery", "analytics", "oauth"],
        ),
    ],
)

request_handler = DefaultRequestHandler(
    agent_executor=AerospaceAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

a2a_app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=request_handler,
)

# Starlette/ASGI app that `uvicorn app.main:app` serves. `a2a_app.build()`
# mounts the standard A2A JSON-RPC routes (agent card discovery at
# `/.well-known/agent-card.json`, and the RPC endpoint at `/a2a`), per
# https://a2a-protocol.org/latest/tutorials/python/6-running-the-server/
app = a2a_app.build()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        reload=bool(os.environ.get("DEV_RELOAD")),
    )
