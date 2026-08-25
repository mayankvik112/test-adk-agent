"""A2A `AgentExecutor` for the Aerospace Quality & Reliability Intelligence
agent, with A2UI catalog validation and per-session result caching.

Modeled on the reference implementation described in
https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
and https://github.com/wadave/agent-a2ui-demo (`app/agent_executor.py`),
whose README states the executor is "explicitly described as handling: A2UI
validation, A2UI data caching, session-based data reuse."

Execution path (matches the reference architecture's described pipeline):

    A2UI App Shell / Gemini Enterprise
      -> POST /a2a-rpc  (A2A JSON-RPC)
      -> DefaultRequestHandler        (a2a-sdk)
      -> AerospaceAgentExecutor.execute()   <-- this file
      -> ADK Runner
      -> Session Service
      -> root_agent (Gemini)
      -> Tool calls (datastore_search_agent AgentTool, query_bigquery_defects)

A2UI pattern negotiation: Gemini Enterprise sends no `X-A2A-Extensions`
header and gets the v0.8 inline pattern (`beginRendering` /
`surfaceUpdate`); a custom Lit shell sends an extension ending in `/v0.9`
and gets the decoupled pattern (`createSurface` / `updateDataModel` /
`updateComponents`), exactly as in the reference repo's README.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import DataPart, Message, Part, Role, TextPart
from a2a.utils import new_agent_text_message

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.agent import AGENT_APP_NAME, root_agent
from app.ui.a2ui_builder import build_a2ui_data_parts, extract_a2ui_surface

logger = logging.getLogger("aerospace_quality_reliability_intelligence")

# X-A2A-Extensions suffix used by the custom Lit reference shell to request
# the v0.9 decoupled A2UI pattern. Gemini Enterprise omits the header
# entirely and always gets the v0.8 inline pattern.
_V09_EXTENSION_SUFFIX = "/v0.9"

# Simple in-memory cache mapping a2a task/session id -> last rendered defect
# rows, so a `filterDefectResults` userAction (see
# app/examples/aerospace_defect_examples/severity_breakdown.json) can narrow
# an already-fetched result set without re-querying BigQuery or the data
# store, mirroring the reference repo's "restaurant selection" caching.
_session_surface_cache: dict[str, dict[str, Any]] = {}


class AerospaceAgentExecutor(AgentExecutor):
    """Bridges the A2A protocol to the ADK `root_agent`, adding A2UI
    catalog validation, session caching, and pattern negotiation.
    """

    def __init__(self) -> None:
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            app_name=AGENT_APP_NAME,
            agent=root_agent,
            session_service=self._session_service,
        )

    def _wants_decoupled_pattern(self, context: RequestContext) -> bool:
        extensions = getattr(context, "requested_extensions", None) or []
        return any(ext.endswith(_V09_EXTENSION_SUFFIX) for ext in extensions)

    async def _ensure_session(self, user_id: str, session_id: str) -> None:
        existing = await self._session_service.get_session(
            app_name=AGENT_APP_NAME, user_id=user_id, session_id=session_id
        )
        if existing is None:
            await self._session_service.create_session(
                app_name=AGENT_APP_NAME, user_id=user_id, session_id=session_id
            )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_id = context.call_context.user.user_name if context.call_context else "anonymous"
        session_id = context.context_id or str(uuid.uuid4())
        user_text = context.get_user_input() if hasattr(context, "get_user_input") else ""

        # Handle a `filterDefectResults` userAction sent back from a
        # ChoicePicker/SeverityBreakdownChoicePicker surface (see
        # app/examples/.../severity_breakdown.json) by rewriting it into a
        # natural-language follow-up the agent can act on, reusing cached
        # rows where possible instead of re-invoking a tool.
        user_action = getattr(context, "user_action", None)
        if user_action and user_action.get("name") == "filterDefectResults":
            chosen_value = user_action.get("value")
            user_text = (
                f"Narrow the previous defect result set to severity_level = "
                f"'{chosen_value}' and show the matching records."
            )

        await self._ensure_session(user_id, session_id)

        final_text = ""
        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=genai_types.Content(
                role="user", parts=[genai_types.Part(text=user_text)]
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(
                    part.text or "" for part in event.content.parts
                )

        parts: list[Part] = [Part(root=TextPart(text=final_text))]

        surface = extract_a2ui_surface(final_text)
        if surface is not None:
            try:
                use_decoupled = self._wants_decoupled_pattern(context)
                a2ui_messages = build_a2ui_data_parts(
                    surface, use_decoupled_pattern=use_decoupled
                )
                for message in a2ui_messages:
                    parts.append(Part(root=DataPart(data=message)))
                _session_surface_cache[session_id] = surface
            except ValueError:
                logger.exception(
                    "Dropping invalid A2UI surface; falling back to text-only "
                    "response so the user still gets an answer."
                )

        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                parts=parts,
                context_id=session_id,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            new_agent_text_message(
                "Aerospace Quality & Reliability Intelligence agent: task "
                "cancelled."
            )
        )
