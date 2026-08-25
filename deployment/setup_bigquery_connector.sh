#!/usr/bin/env bash
# Creates (or refreshes) the Gemini Enterprise Data Store that ingests the
# aircraft-defects BigQuery table, following
# https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery
#
# The five grounding fields (defect_id, aircraft_model, component_category,
# severity_level, defect_description) are ingested as a `custom` schema
# document store, with `defect_id` supplying the document ID.
#
# Usage:
#   PROJECT_ID=my-project LOCATION=global DATASET_ID=aerospace_quality \
#   TABLE_ID=aircraft_defects DATASTORE_ID=aerospace-defects-datastore \
#   ./deployment/setup_bigquery_connector.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
LOCATION="${LOCATION:-global}"
DATASET_ID="${DATASET_ID:?Set DATASET_ID, e.g. aerospace_quality}"
TABLE_ID="${TABLE_ID:?Set TABLE_ID, e.g. aircraft_defects}"
DATASTORE_ID="${DATASTORE_ID:-aerospace-defects-datastore}"
DATASTORE_DISPLAY_NAME="${DATASTORE_DISPLAY_NAME:-Aerospace Defects Data Store}"

echo "==> [1/3] Creating Gemini Enterprise data store '${DATASTORE_ID}' in project ${PROJECT_ID} (${LOCATION})"
curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://discoveryengine.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/collections/default_collection/dataStores?dataStoreId=${DATASTORE_ID}" \
  -d "{
    \"displayName\": \"${DATASTORE_DISPLAY_NAME}\",
    \"industryVertical\": \"GENERIC\",
    \"solutionTypes\": [\"SOLUTION_TYPE_SEARCH\"]
  }"

echo "==> [2/3] Importing ${PROJECT_ID}.${DATASET_ID}.${TABLE_ID} into data store '${DATASTORE_ID}'"
# dataSchema=custom accepts the raw 5-column table as-is; defect_id is used
# directly as the document id (idField), per the "custom" schema rules in
# https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery#rest-import
curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://discoveryengine.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/collections/default_collection/dataStores/${DATASTORE_ID}/branches/0/documents:import" \
  -d "{
    \"bigquerySource\": {
      \"projectId\": \"${PROJECT_ID}\",
      \"datasetId\": \"${DATASET_ID}\",
      \"tableId\": \"${TABLE_ID}\",
      \"dataSchema\": \"custom\"
    },
    \"reconciliationMode\": \"FULL\",
    \"idField\": \"defect_id\"
  }"

echo "==> [3/3] Done. Resulting datastore resource id for AEROSPACE_DEFECTS_DATASTORE_ID:"
echo "projects/${PROJECT_ID}/locations/${LOCATION}/collections/default_collection/dataStores/${DATASTORE_ID}"
echo
echo "If the BigQuery table lives in a different project than ${PROJECT_ID}, first grant"
echo "  roles/bigquery.jobUser and roles/bigquery.dataEditor"
echo "to service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com"
echo "on the source project, per the prerequisites in"
echo "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery#prerequisites-and-iam-roles"
echo
echo "Prefer a UI-driven, periodically syncing connector instead? Use the Google Cloud"
echo "console flow (Gemini Enterprise > Data Stores > Create Data Store > BigQuery > Periodic),"
echo "documented at the same URL above under 'Periodic BigQuery syncing'."
