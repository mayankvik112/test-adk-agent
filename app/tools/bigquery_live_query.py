"""Read-only, 3-legged-OAuth-authenticated live BigQuery tool.

Complements `sub_agents.datastore_search_agent`: the Vertex AI Search
sub-agent answers retrieval/narrative questions from the Gemini Enterprise
Data Store snapshot; this tool answers aggregation/analytics questions by
querying the live BigQuery table directly, using the *signed-in engineer's*
own OAuth token (obtained through the Agent Identity 3-legged OAuth auth
provider — see `app/auth/auth_provider.py` and
https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2).

Pattern follows the "Authenticated function tool" example in the 3LO guide:
the function receives a `google.adk.auth.auth_credential.AuthCredential` as
its first parameter, ADK injects it after the user completes consent, and the
function extracts a bearer token from it to call the BigQuery REST API on
the user's behalf (never a shared service account).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from google.adk.auth.auth_credential import AuthCredential
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool

from app.auth.auth_provider import get_bigquery_auth_config

BIGQUERY_PROJECT_ID = os.environ.get("BIGQUERY_PROJECT_ID", "YOUR_PROJECT_ID")
BIGQUERY_DATASET = os.environ.get("BIGQUERY_DATASET", "aerospace_quality")
BIGQUERY_TABLE = os.environ.get("BIGQUERY_TABLE", "aircraft_defects")

_ALLOWED_COLUMNS = {
    "defect_id",
    "aircraft_model",
    "component_category",
    "severity_level",
    "defect_description",
}

_BIGQUERY_QUERY_URL = (
    f"https://bigquery.googleapis.com/bigquery/v2/projects/"
    f"{BIGQUERY_PROJECT_ID}/queries"
)


class BigQueryToolError(RuntimeError):
    """Raised when the live BigQuery query cannot be executed or validated."""


def _extract_bearer_token(credential: AuthCredential) -> str:
    if credential and credential.http and credential.http.credentials:
        token = credential.http.credentials.token
        if token:
            return token
    raise BigQueryToolError(
        "No BigQuery OAuth token available. The end user must complete the "
        "3-legged OAuth consent flow for the "
        f"'{os.environ.get('BIGQUERY_AUTH_PROVIDER_NAME', 'aerospace-bigquery-3lo-authprovider')}' "
        "auth provider before this tool can run."
    )


def _validate_select_only(sql: str) -> None:
    """Defense-in-depth guard: only ever allow read-only SELECT statements
    against the defects table, scoped to the five known columns.
    """
    normalized = " ".join(sql.strip().split()).rstrip(";")
    lowered = normalized.lower()
    if not lowered.startswith("select"):
        raise BigQueryToolError("Only SELECT statements are permitted.")
    forbidden = (
        "insert",
        "update",
        "delete",
        "merge",
        "drop",
        "create",
        "alter",
        "truncate",
        "grant",
        "call",
        "--",
        ";",
    )
    if any(token in lowered for token in forbidden):
        raise BigQueryToolError(
            "Query rejected: only simple read-only SELECT statements over "
            f"`{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}` are "
            "allowed."
        )
    qualified_table = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}".lower()
    if qualified_table not in lowered and f"`{qualified_table}`" not in lowered:
        raise BigQueryToolError(
            "Query rejected: it must reference the defects table "
            f"`{qualified_table}`."
        )


async def query_bigquery_defects(
    credential: AuthCredential,
    sql_query: str,
) -> dict[str, Any]:
    """Runs a read-only SQL query against the live aircraft defects table.

    Args:
        credential: injected automatically by ADK after the end user
            completes the 3-legged OAuth consent flow for the BigQuery
            auth provider. Do not pass this manually — it is populated by
            the framework.
        sql_query: a single read-only `SELECT` statement against
            `{project}.{dataset}.{table}` (see module constants). Use
            standard SQL. Only the five defect columns (defect_id,
            aircraft_model, component_category, severity_level,
            defect_description) and standard aggregate functions
            (COUNT, GROUP BY, etc.) are expected.

    Returns:
        A dict with `rows` (list of dict rows) and `total_rows`, or an
        `error` key describing why the query could not be run.
    """
    try:
        _validate_select_only(sql_query)
        token = _extract_bearer_token(credential)
    except BigQueryToolError as exc:
        return {"error": str(exc)}

    payload = {
        "query": sql_query,
        "useLegacySql": False,
        "maxResults": 200,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _BIGQUERY_QUERY_URL,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        return {"error": f"BigQuery request failed: {exc}"}

    schema_fields = [
        field["name"] for field in result.get("schema", {}).get("fields", [])
    ]
    rows = [
        dict(zip(schema_fields, [cell.get("v") for cell in row.get("f", [])]))
        for row in result.get("rows", [])
    ]
    return {
        "rows": rows,
        "total_rows": result.get("totalRows", str(len(rows))),
    }


def build_bigquery_defects_tool() -> AuthenticatedFunctionTool:
    """Wraps `query_bigquery_defects` with its 3-legged OAuth `AuthConfig`."""
    return AuthenticatedFunctionTool(
        func=query_bigquery_defects,
        auth_config=get_bigquery_auth_config(),
    )
