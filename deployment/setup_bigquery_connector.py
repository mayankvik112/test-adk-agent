"""Creates (or refreshes) the Gemini Enterprise Data Store that ingests the
aircraft-defects BigQuery table, following
https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery

The five grounding fields (defect_id, aircraft_model, component_category,
severity_level, defect_description) are ingested as a `custom` schema
document store, with `defect_id` supplying the document ID.

Cross-platform (Windows/macOS/Linux) equivalent of the previous
`setup_bigquery_connector.sh`. Requires the `gcloud` CLI to be installed
and authenticated (`gcloud init`), and the project's dependencies synced.

Usage:
    uv run python -m deployment.setup_bigquery_connector

Environment variables (with defaults):
    PROJECT_ID           (required)
    LOCATION              default: global
    DATASET_ID            (required, e.g. aerospace_quality)
    TABLE_ID               (required, e.g. aircraft_defects)
    DATASTORE_ID           default: aerospace-defects-datastore
    DATASTORE_DISPLAY_NAME default: "Aerospace Defects Data Store"
"""

from __future__ import annotations

import os
import sys

import httpx

from ._gcloud import access_token

DISCOVERY_ENGINE_BASE = "https://discoveryengine.googleapis.com/v1"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Set the {name} environment variable before running this script.")
    return value


def main() -> None:
    project_id = _require_env("PROJECT_ID")
    location = os.environ.get("LOCATION", "global")
    dataset_id = _require_env("DATASET_ID")
    table_id = _require_env("TABLE_ID")
    datastore_id = os.environ.get("DATASTORE_ID", "aerospace-defects-datastore")
    datastore_display_name = os.environ.get(
        "DATASTORE_DISPLAY_NAME", "Aerospace Defects Data Store"
    )

    headers = {
        "Authorization": f"Bearer {access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id,
    }
    collection = (
        f"projects/{project_id}/locations/{location}/collections/default_collection"
    )

    print(f"==> [1/3] Creating Gemini Enterprise data store '{datastore_id}' "
          f"in project {project_id} ({location})")
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{DISCOVERY_ENGINE_BASE}/{collection}/dataStores",
            params={"dataStoreId": datastore_id},
            headers=headers,
            json={
                "displayName": datastore_display_name,
                "industryVertical": "GENERIC",
                "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
            },
        )
        print(resp.status_code, resp.text[:2000])

        print(
            f"\n==> [2/3] Importing {project_id}.{dataset_id}.{table_id} into "
            f"data store '{datastore_id}'"
        )
        # dataSchema=custom accepts the raw 5-column table as-is; defect_id is
        # used directly as the document id (idField), per the "custom" schema
        # rules in
        # https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery#rest-import
        resp = client.post(
            f"{DISCOVERY_ENGINE_BASE}/{collection}/dataStores/{datastore_id}"
            f"/branches/0/documents:import",
            headers=headers,
            json={
                "bigquerySource": {
                    "projectId": project_id,
                    "datasetId": dataset_id,
                    "tableId": table_id,
                    "dataSchema": "custom",
                },
                "reconciliationMode": "FULL",
                "idField": "defect_id",
            },
        )
        print(resp.status_code, resp.text[:2000])

    datastore_resource = (
        f"projects/{project_id}/locations/{location}/collections/"
        f"default_collection/dataStores/{datastore_id}"
    )
    print(f"\n==> [3/3] Done. Resulting datastore resource id for "
          f"AEROSPACE_DEFECTS_DATASTORE_ID:\n{datastore_resource}")
    print(
        "\nIf the BigQuery table lives in a different project than "
        f"{project_id}, first grant roles/bigquery.jobUser and "
        "roles/bigquery.dataEditor to "
        "service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com "
        "on the source project, per the prerequisites in "
        "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery#prerequisites-and-iam-roles"
    )
    print(
        "\nPrefer a UI-driven, periodically syncing connector instead? Use the "
        "Google Cloud console flow (Gemini Enterprise > Data Stores > Create "
        "Data Store > BigQuery > Periodic), documented at the same URL above "
        "under 'Periodic BigQuery syncing'."
    )


if __name__ == "__main__":
    main()
