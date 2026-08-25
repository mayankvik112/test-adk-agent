"""Sub-agent that wraps the built-in `VertexAiSearchTool`.

ADK currently restricts each agent to a single built-in tool (no other tools,
of any kind, can be attached to an agent that already has a built-in tool
such as `VertexAiSearchTool`). To combine grounded search over the
BigQuery-backed Gemini Enterprise Data Store with a second, custom
(3-legged-OAuth-authenticated) BigQuery tool on the same root agent, the
search capability is isolated in its own single-tool agent and exposed to the
root agent as an `AgentTool`. This mirrors the `search_agent` pattern used in
Google's A2UI reference implementation
(https://github.com/wadave/agent-a2ui-demo, `app/sub_agents.py`).

Docs referenced:
- https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery
- https://adk.dev/grounding/grounding_with_search/  (bypass_multi_tools_limit)
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools import VertexAiSearchTool

from app.prompts import DATASTORE_SEARCH_AGENT_INSTRUCTION

# Resource ID of the Gemini Enterprise Data Store that the BigQuery connector
# populates from the aircraft-defects table. Format documented at
# https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery :
#   projects/<PROJECT_ID>/locations/<LOCATION>/collections/default_collection/dataStores/<DATASTORE_ID>
DEFECTS_DATASTORE_ID = os.environ.get(
    "AEROSPACE_DEFECTS_DATASTORE_ID",
    "projects/YOUR_PROJECT_ID/locations/global/collections/default_collection/"
    "dataStores/aerospace-defects-datastore",
)

SEARCH_AGENT_MODEL = os.environ.get("SEARCH_AGENT_MODEL", "gemini-2.5-flash")


def build_datastore_search_agent() -> Agent:
    """Builds the single-purpose Vertex AI Search sub-agent.

    Returns an `Agent` configured with exactly one tool
    (`VertexAiSearchTool`) pointed at the BigQuery-connector-fed Gemini
    Enterprise Data Store described in the task's data domain (defect_id,
    aircraft_model, component_category, severity_level,
    defect_description).
    """
    vertex_search_tool = VertexAiSearchTool(data_store_id=DEFECTS_DATASTORE_ID)

    return Agent(
        name="datastore_search_agent",
        model=SEARCH_AGENT_MODEL,
        description=(
            "Searches the BigQuery-connector-backed Gemini Enterprise Data "
            "Store of aircraft defect records (defect_id, aircraft_model, "
            "component_category, severity_level, defect_description)."
        ),
        instruction=DATASTORE_SEARCH_AGENT_INSTRUCTION,
        tools=[vertex_search_tool],
    )
