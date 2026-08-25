# Architecture

## Design goals

1. Ground every answer in the aircraft-defects dataset via the **existing**
   BigQuery connector / Gemini Enterprise Data Store — never let the model
   answer from its own knowledge.
2. Let each engineer query live BigQuery **as themselves**, with their own
   IAM permissions, rather than through a shared service account.
3. Present results as structured, interactive UI (tables, severity badges,
   drill-down choice pickers) instead of walls of text, using the native
   A2UI protocol Gemini Enterprise already knows how to render.

## Two retrieval paths, one agent

The dataset is reachable through two different tools with two different
trust models, and the root agent picks between them based on the user's
question (see the tool-selection rules in `app/prompts.py`):

| Path | Tool | Backing store | Auth | Best for |
|---|---|---|---|---|
| A | `datastore_search_agent` (`AgentTool` wrapping `VertexAiSearchTool`) | Gemini Enterprise Data Store fed by the BigQuery connector | Data Store's own configured access (ACLs pulled from BigQuery if `aclEnabled`) | Natural-language / semantic search: "show me critical fuselage defects on the 787-9" |
| B | `query_bigquery_defects` (`AuthenticatedFunctionTool`) | Live BigQuery `aircraft_defects` table | 3-legged OAuth, per signed-in engineer | Precise aggregations/filters: "how many Major landing-gear defects were logged this quarter, broken down by aircraft model" |

### Why `VertexAiSearchTool` lives in its own sub-agent

ADK enforces that **a single agent may use at most one built-in tool, and
no other tool of any type in the same agent** when that built-in tool is
present (confirmed against the current ADK tool documentation while
building this agent). Since the root agent also needs the custom
`query_bigquery_defects` function tool, `VertexAiSearchTool` cannot live on
the root agent directly. `app/sub_agents/datastore_search_agent.py`
isolates it in its own single-purpose `Agent`, which the root agent then
calls through `google.adk.tools.agent_tool.AgentTool` — the same pattern
the [wadave/agent-a2ui-demo](https://github.com/wadave/agent-a2ui-demo)
reference repo uses to isolate `GoogleSearchTool`.

### Why `query_bigquery_defects` uses 3-legged OAuth, not a service account

The task requires authenticating "using 3-legged OAuth", per
[Authenticate using 3-legged OAuth with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2).
`app/auth/auth_provider.py` registers a `GcpAuthProvider` with ADK's
`CredentialManager` and builds an `AuthConfig` around a
`GcpAuthProviderScheme` pointing at the Agent Identity auth-provider
resource (`projects/<P>/locations/<L>/authProviders/<NAME>`), scoped to
`https://www.googleapis.com/auth/bigquery`. `app/tools/bigquery_live_query.py`
wraps the actual query function in `AuthenticatedFunctionTool`, so ADK
automatically triggers the OAuth consent flow the first time a given
engineer uses the tool, then injects the resulting per-user
`AuthCredential` (containing a short-lived bearer token) into the function
on every subsequent call — the query genuinely runs under BigQuery's
existing IAM permissions for that person, not the agent's own identity.

### SQL guardrails

Because the OAuth-authenticated path executes arbitrary text the LLM
constructs, `_validate_select_only()` in `bigquery_live_query.py` rejects
anything that is not a single `SELECT` statement scoped to the configured
`{project}.{dataset}.{table}` (env-configured, defaults to
`aerospace_quality.aircraft_defects`) and blocks DML/DDL keywords and
statement chaining before the query ever reaches the BigQuery REST API.

## A2UI: from LLM text to rendered UI

1. `app/prompts.py`'s `ROOT_AGENT_INSTRUCTION` tells the model to emit a
   fenced ` ```json ` block containing an `a2ui_surface` object whenever it
   returns defect rows or aggregations, using one of the catalog's
   component names (`DefectResultsTable`, `SeverityBreakdownChoicePicker`).
   Two few-shot examples live in `app/examples/aerospace_defect_examples/`.
2. `app/agent_executor.py::AerospaceAgentExecutor.execute()` runs the ADK
   `Runner`, takes the final text event, and calls
   `app/ui/a2ui_builder.py::extract_a2ui_surface()` to pull out the JSON
   object.
3. `extract_a2ui_surface()`'s result is validated against
   `app/catalog_schemas/0.8/aerospace_defect_catalog.json` — an unknown
   `component` raises rather than silently rendering nothing.
4. `build_a2ui_data_parts()` converts the validated surface into the A2UI
   wire format Gemini Enterprise expects. Two shapes exist because the
   ecosystem is mid-migration, per
   [Developer's guide to Gemini Enterprise and A2UI integration](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration):
   - **Inline pattern** (`beginRendering` + `surfaceUpdate`, catalog v0.8) —
     what Gemini Enterprise's built-in chat renderer supports today.
   - **Decoupled pattern** (`createSurface` + `updateDataModel` +
     `updateComponents`, v0.9) — the direction the protocol is moving,
     used by custom frontends (e.g. the Lit shell in
     `wadave/agent-a2ui-demo/frontend`).
   `_wants_decoupled_pattern()` in `agent_executor.py` negotiates which
   shape to emit by checking the `X-A2A-Extensions` request header for a
   `/v0.9` suffix, falling back to the inline v0.8 pattern Gemini
   Enterprise itself sends.
5. Each shape is wrapped as an A2A `DataPart` with
   `mimeType="application/json+a2ui"` alongside a plain-text `TextPart`
   fallback, and enqueued as a single A2A `Message` — so any A2A client
   that doesn't understand A2UI still gets a sensible text answer.
6. `SeverityBreakdownChoicePicker` surfaces include a
   `userActionName: "filterDefectResults"`; when the user picks an option,
   Gemini Enterprise sends that action back through A2A and
   `agent_executor.py` rewrites it into a natural-language follow-up
   ("Show Major severity Main Landing Gear defects") before re-invoking the
   Runner, closing the interaction loop.

## Deployment topology

```
deployment/setup_bigquery_connector.sh   -> Gemini Enterprise Data Store (path A)
deployment/setup_auth_provider.sh        -> Agent Identity 3LO auth provider (path B)
app/main.py (Dockerfile)  -> Cloud Run / GKE A2A endpoint  ─┐
   or                                                        ├─> deployment/register_gemini_enterprise.sh
deployment/deploy_agent_engine.py -> Vertex AI Agent Engine ─┘   -> Gemini Enterprise agent catalog
```

Both deployment targets set `identity_type: AGENT_IDENTITY`
(`.agent_engine_config.json` for the `adk deploy agent_engine` CLI path, or
the `config` dict passed to `client.agent_engines.create()` in
`deploy_agent_engine.py`), which is the flag documented in the 3LO guide
as required for Agent Identity / 3-legged OAuth to function once deployed.

## Reference sources

- [Connect to BigQuery with Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery)
- [Authenticate using 3-legged OAuth with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2)
- [Developer's guide to Gemini Enterprise and A2UI integration](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration)
- [wadave/agent-a2ui-demo](https://github.com/wadave/agent-a2ui-demo)
