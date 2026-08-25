# Aerospace Quality & Reliability Intelligence

A **Pro Code** Google Agent Development Kit (ADK) agent for **Gemini
Enterprise** that lets quality/reliability engineers search and analyze
aircraft defect records grounded in an existing BigQuery connector, and
renders results as native, interactive UI via **A2UI** instead of plain
text.

## Data domain

Every defect record has exactly five fields:

| Field | Description |
|---|---|
| `defect_id` | Unique identifier |
| `aircraft_model` | e.g. Boeing 787-9 Dreamliner, Airbus A350-1000 |
| `component_category` | e.g. Fuselage, Composite Skin, Main Landing Gear |
| `severity_level` | Critical, Major, or Minor |
| `defect_description` | Rich engineering narrative |

## What this repo implements

1. **Grounded search over the existing BigQuery connector.** The Gemini
   Enterprise Data Store that the BigQuery connector already populates from
   the `aircraft_defects` table is queried through ADK's built-in
   `VertexAiSearchTool`, isolated in its own single-purpose
   `datastore_search_agent` and exposed to the root agent as an `AgentTool`
   (ADK currently allows only one built-in tool per agent — see
   `app/sub_agents/datastore_search_agent.py`).
   Docs: [Connect to BigQuery with Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery)
2. **3-legged OAuth (3LO) authentication to BigQuery.** A second tool,
   `query_bigquery_defects` (`app/tools/bigquery_live_query.py`), runs
   read-only, live SQL directly against BigQuery using the **signed-in
   engineer's own OAuth token**, obtained through an Agent Identity 3LO auth
   provider (`app/auth/auth_provider.py`, provisioned by
   `deployment/setup_auth_provider.py`). BigQuery's own row/column-level
   security applies exactly as if the engineer ran the query themselves —
   no shared service account is used for this path.
   Docs: [Authenticate using 3-legged OAuth with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2)
3. **Custom UI via A2UI.** The root agent's answers embed a structured
   `a2ui_surface` object (see `app/prompts.py` +
   `app/examples/aerospace_defect_examples/`); the A2A executor
   (`app/agent_executor.py`) validates it against a custom catalog
   (`app/catalog_schemas/0.8/aerospace_defect_catalog.json` —
   `DefectResultsTable`, `SeverityBadge`, `SeverityBreakdownChoicePicker`)
   and turns it into native A2UI protocol messages that Gemini Enterprise
   renders with its own built-in renderer.
   Docs: [Developer's guide to Gemini Enterprise and A2UI integration](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration) ·
   Reference implementation: [wadave/agent-a2ui-demo](https://github.com/wadave/agent-a2ui-demo)

## Architecture

```
                     ┌─────────────────────────────┐
                     │      Gemini Enterprise       │
                     │ (chat shell + A2UI renderer  │
                     │  + A2A transport client)     │
                     └───────────────┬─────────────┘
                                     │ A2A JSON-RPC  (POST /a2a)
                                     ▼
                     ┌─────────────────────────────┐
                     │ AerospaceAgentExecutor        │  app/agent_executor.py
                     │  - A2UI catalog validation     │
                     │  - session result caching      │
                     │  - inline (v0.8) vs decoupled   │
                     │    (v0.9) pattern negotiation   │
                     └───────────────┬─────────────┘
                                     │ ADK Runner
                                     ▼
                     ┌─────────────────────────────┐
                     │   root_agent (Gemini 2.5)      │  app/agent.py
                     └──────┬───────────────┬────────┘
                            │               │
              AgentTool     │               │  AuthenticatedFunctionTool
                            ▼               ▼               (3-legged OAuth)
        ┌───────────────────────────┐  ┌────────────────────────────────┐
        │  datastore_search_agent    │  │  query_bigquery_defects          │
        │  VertexAiSearchTool        │  │  live BigQuery SQL, user's own   │
        │                            │  │  OAuth token via Agent Identity  │
        └─────────────┬──────────────┘  └───────────────┬──────────────┘
                       │                                  │
                       ▼                                  ▼
      ┌────────────────────────────────┐     ┌───────────────────────────┐
      │ Gemini Enterprise Data Store    │     │  BigQuery aircraft_defects   │
      │ (populated by the BigQuery       │◄────┤  table (live, user-scoped     │
      │  connector — one-time or         │ sync│  IAM permissions)              │
      │  periodic sync)                  │     │                               │
      └────────────────────────────────┘     └───────────────────────────┘
```

## Repository layout

```
app/
├── agent.py                 # root_agent + App wrapper (VertexAiSearchTool sub-agent + BigQuery 3LO tool)
├── agent_executor.py        # A2A AgentExecutor: runs ADK Runner, validates/caches A2UI surfaces
├── main.py                  # uvicorn entry point exposing the A2A endpoint (agent card + JSON-RPC)
├── prompts.py                # root + sub-agent instructions, incl. the A2UI response convention
├── sub_agents/
│   └── datastore_search_agent.py   # single-tool VertexAiSearchTool agent (BigQuery-connector datastore)
├── tools/
│   └── bigquery_live_query.py      # 3-legged-OAuth-authenticated, read-only live BigQuery tool
├── auth/
│   └── auth_provider.py            # Agent Identity 3LO GcpAuthProviderScheme/AuthConfig wiring
├── ui/
│   └── a2ui_builder.py             # a2ui_surface JSON -> A2UI DataParts (inline v0.8 / decoupled v0.9)
├── catalog_schemas/0.8/
│   └── aerospace_defect_catalog.json   # DefectResultsTable / DefectRow / SeverityBadge / ChoicePicker
└── examples/aerospace_defect_examples/  # few-shot A2UI examples for the LLM
deployment/
├── _gcloud.py                     # cross-platform gcloud subprocess helper (Windows/macOS/Linux)
├── setup_bigquery_connector.py    # creates the Gemini Enterprise Data Store from the BigQuery table
├── setup_auth_provider.py         # creates the Agent Identity 3-legged OAuth auth provider
├── register_gemini_enterprise.py  # registers the A2A endpoint with Gemini Enterprise
└── deploy_agent_engine.py         # deploys to Vertex AI Agent Engine with Agent Identity enabled
tests/
└── test_agent_smoke.py            # pure-logic tests for the A2UI builder + SQL guardrail
Dockerfile                          # uv-based image for the A2A endpoint (Cloud Run / GKE)
docker-compose.yml                  # local dev loop: `docker compose up --build`
pyproject.toml / uv.lock             # dependencies, resolved and pinned with uv
```

All deployment scripts are plain Python (no bash/PowerShell-only syntax
anywhere in the repo), run as modules from the repo root with `uv run`, so
they work identically on Windows, macOS, and Linux — the only external
requirement is the `gcloud` CLI on PATH (it has a native Windows
installer).

## Setup

### 1. Point the agent at the existing BigQuery connector / Data Store

If the BigQuery connector and Gemini Enterprise Data Store already exist
(as stated in the task), just copy its resource ID into `.env`:

```
AEROSPACE_DEFECTS_DATASTORE_ID=projects/<PROJECT_ID>/locations/<LOCATION>/collections/default_collection/dataStores/<DATASTORE_ID>
```

Otherwise, create it with:

```bash
# macOS / Linux / Windows (PowerShell, cmd, or bash) — set the env vars for
# your shell, then run the module from the repo root.
PROJECT_ID=<project> DATASET_ID=aerospace_quality TABLE_ID=aircraft_defects \
  uv run python -m deployment.setup_bigquery_connector
```

```powershell
# Windows PowerShell equivalent
$env:PROJECT_ID="<project>"; $env:DATASET_ID="aerospace_quality"; $env:TABLE_ID="aircraft_defects"
uv run python -m deployment.setup_bigquery_connector
```

which follows the one-time/`custom` schema BigQuery import flow documented
at [Connect to BigQuery with Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery#one-time-bigquery-ingestion-using-rest).
For cross-project imports, grant `roles/bigquery.jobUser` and
`roles/bigquery.dataEditor` to
`service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com`
on the source project first, per the same doc's prerequisites.

### 2. Provision the 3-legged OAuth auth provider

```bash
gcloud services enable agentidentity.googleapis.com --project=<project>
PROJECT_ID=<project> LOCATION=us-west1 \
  OAUTH_CLIENT_ID=<client-id> OAUTH_CLIENT_SECRET=<client-secret> \
  uv run python -m deployment.setup_auth_provider
```

This walks through the OAuth consent screen / Web-application OAuth client
/ redirect-URI / `gcloud agent-identity auth-providers create` steps from
[Authenticate using 3-legged OAuth with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#required-setup).
The BigQuery scope used is `https://www.googleapis.com/auth/bigquery`.

### 3. Install dependencies and run locally

Two equivalent ways to run locally — pick whichever fits your workflow.
Both work the same on Windows, macOS, and Linux.

**Option A — uv directly (no Docker), good for iterating on the ADK
agent/OAuth consent flow:**

```bash
uv sync                 # installs into a local .venv, pinned by uv.lock
cp .env.example .env     # fill in project/location/datastore/auth-provider values
uv run adk web app       # `adk web` — exercise the 3LO consent flow interactively
# or
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload   # the real A2A endpoint
```

**Option B — Docker (matches the production container exactly):**

```bash
cp .env.example .env
docker compose up --build   # A2A endpoint on http://localhost:8080, hot-reloads on code edits
```

On Windows, install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
with the WSL2 backend and run the same `docker compose up --build` command
from PowerShell, cmd, or a WSL shell — the container itself is always
Linux, so nothing else changes.

### 4. Deploy

```bash
uv run python -m deployment.deploy_agent_engine   # Vertex AI Agent Engine, AGENT_IDENTITY enabled
# then grant the deployed engine access to the auth provider:
ENGINE_ID=<numeric id from step above> uv run python -m deployment.setup_auth_provider
```

or build the production container from the same `Dockerfile` and push it
to Cloud Run/GKE:

```bash
docker build -t aerospace-quality-reliability-agent .
docker tag aerospace-quality-reliability-agent <region>-docker.pkg.dev/<project>/<repo>/aerospace-quality-reliability-agent
docker push <region>-docker.pkg.dev/<project>/<repo>/aerospace-quality-reliability-agent
gcloud run deploy aerospace-quality-reliability-agent \
  --image <region>-docker.pkg.dev/<project>/<repo>/aerospace-quality-reliability-agent \
  --project <project> --region <region>
```

then register the deployed endpoint with Gemini Enterprise:

```bash
AGENT_PUBLIC_URL=https://<cloud-run-url> ASSISTANT_ID=<assistant-id> \
  uv run python -m deployment.register_gemini_enterprise
```

An administrator then shares the agent from the Gemini Enterprise agent
catalog with the intended engineers, per
[Developer's guide to Gemini Enterprise and A2UI integration](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration#integrating-an-adk-agent-with-gemini-enterprise).

## A2UI response contract

Every user-visible defect result set is emitted as a fenced ` ```json `
block containing an `a2ui_surface` key (see `app/prompts.py` and
`app/examples/aerospace_defect_examples/*.json` for full examples):

```json
{
  "a2ui_surface": {
    "component": "DefectResultsTable",
    "title": "Critical Fuselage Defects — Boeing 787-9 Dreamliner",
    "result_count": 3,
    "applied_filters": ["aircraft_model = Boeing 787-9 Dreamliner", "severity_level = Critical"],
    "rows": [
      { "defect_id": "DEF-100482", "aircraft_model": "Boeing 787-9 Dreamliner",
        "component_category": "Fuselage", "severity_level": "Critical",
        "defect_description": "Sub-surface delamination detected at frame station 47..." }
    ]
  }
}
```

`app/agent_executor.py` validates `component` against
`app/catalog_schemas/0.8/aerospace_defect_catalog.json` and converts it to
the A2UI protocol messages Gemini Enterprise expects
(`beginRendering`/`surfaceUpdate` for the v0.8 inline pattern Gemini
Enterprise renders today, or `createSurface`/`updateDataModel`/
`updateComponents` for a v0.9 custom Lit shell), transported as A2A
`DataPart` objects with MIME type `application/json+a2ui`, exactly as
described in the A2UI integration guide above.

## Testing

```bash
uv run pytest tests -q
```

`tests/test_agent_smoke.py` covers the pieces that don't require live GCP
credentials: A2UI surface extraction/validation and the BigQuery SQL
guardrail (`SELECT`-only, table-scoped).

## Notes on evolving APIs

Gemini Enterprise, ADK, and A2UI are actively evolving products. This repo
pins the documented resource-name formats, scopes, and code patterns as of
the reference docs linked throughout, but always cross-check
`deployment/register_gemini_enterprise.py`'s Discovery Engine "agents"
sub-resource path and the exact ADK/A2A Python package versions in
`pyproject.toml`/`uv.lock` against the current Google Cloud
console/documentation before running in production.

## Windows notes

Everything in this repo is OS-agnostic Python plus a Linux-based Docker
image, so it runs the same on Windows as on macOS/Linux:

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
  (`pip install uv`, `winget install astral-sh.uv`, or the standalone
  installer) and the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
  (native Windows installer) for the non-Docker path.
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  (WSL2 backend) for the container path (`docker compose up --build` /
  `docker build`).
- All `deployment/*.py` scripts are plain Python modules invoked with
  `uv run python -m deployment.<script>` — no bash-only syntax anywhere,
  so PowerShell, cmd, and WSL all work identically.
- `.env` values and environment variables work the same way; PowerShell
  users set them with `$env:NAME="value"` instead of `NAME=value` before
  the command, as shown in the BigQuery connector step above.
