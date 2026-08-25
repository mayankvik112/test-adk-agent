"""Root agent definition: Aerospace Quality & Reliability Intelligence.

Architecture (see ../ARCHITECTURE.md for the full write-up):

  root_agent (Gemini)
    ├── datastore_search_agent  (AgentTool)  -- grounded search over the
    │                                           Gemini Enterprise Data Store
    │                                           that the BigQuery connector
    │                                           already populated. See
    │                                           https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery
    └── query_bigquery_defects (AuthenticatedFunctionTool, 3-legged OAuth)
                                            -- live, user-scoped BigQuery SQL
                                               for aggregations. Auth flow per
                                               https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2

Both tools feed a single conversational agent whose final answers embed an
`a2ui_surface` object (see app/prompts.py + app/ui/a2ui_builder.py) that the
A2A executor (app/agent_executor.py) turns into native A2UI messages so
Gemini Enterprise can render a rich `DefectResultsTable` /
`SeverityBreakdownChoicePicker` UI instead of plain text, following
https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from app.auth.auth_provider import register_gcp_auth_provider
from app.prompts import ROOT_AGENT_INSTRUCTION
from app.sub_agents.datastore_search_agent import build_datastore_search_agent
from app.tools.bigquery_live_query import build_bigquery_defects_tool

ROOT_AGENT_MODEL = os.environ.get("ROOT_AGENT_MODEL", "gemini-2.5-flash")
AGENT_APP_NAME = "aerospace_quality_reliability_intelligence"

# Register the Google Cloud 3-legged OAuth auth provider with ADK's
# CredentialManager once, at import time, per
# https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#agent-code-implementation-with-adk
register_gcp_auth_provider()


def build_root_agent() -> Agent:
    """Assembles the Aerospace Quality & Reliability Intelligence agent."""
    datastore_search_agent = build_datastore_search_agent()
    bigquery_defects_tool = build_bigquery_defects_tool()

    return Agent(
        name="aerospace_quality_reliability_intelligence",
        model=Gemini(
            model=ROOT_AGENT_MODEL,
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
        description=(
            "Aerospace Quality & Reliability Intelligence agent: searches "
            "and analyzes aircraft defect records (defect_id, "
            "aircraft_model, component_category, severity_level, "
            "defect_description) sourced from a BigQuery-connector-backed "
            "Gemini Enterprise Data Store, and renders results as native "
            "A2UI surfaces."
        ),
        instruction=ROOT_AGENT_INSTRUCTION,
        tools=[
            AgentTool(agent=datastore_search_agent),
            bigquery_defects_tool,
        ],
    )


root_agent = build_root_agent()

# `App` wrapper expected by `vertexai.agent_engines.AdkApp` / `adk deploy
# agent_engine`, matching the deployment pattern in
# https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#deploy-the-agent-with-agent-identity-enabled
app = App(
    root_agent=root_agent,
    name=AGENT_APP_NAME,
)
