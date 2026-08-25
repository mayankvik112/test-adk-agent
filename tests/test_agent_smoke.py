"""Lightweight smoke tests that don't require live GCP credentials.

These validate the parts of the codebase that are pure Python logic
(A2UI surface extraction/validation, SQL guardrails), so they can run in CI
without a real Gemini Enterprise Data Store, BigQuery table, or 3-legged
OAuth auth provider configured.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ui.a2ui_builder import (
    build_a2ui_data_parts,
    extract_a2ui_surface,
    load_catalog,
)
from app.tools.bigquery_live_query import _validate_select_only, BigQueryToolError


SAMPLE_AGENT_RESPONSE = """
Found 3 Critical fuselage defects for the Boeing 787-9 Dreamliner.

```json
{
  "a2ui_surface": {
    "component": "DefectResultsTable",
    "title": "Critical Fuselage Defects",
    "result_count": 1,
    "rows": [
      {
        "defect_id": "DEF-100482",
        "aircraft_model": "Boeing 787-9 Dreamliner",
        "component_category": "Fuselage",
        "severity_level": "Critical",
        "defect_description": "Sub-surface delamination detected at frame station 47."
      }
    ]
  }
}
```
"""


def test_load_catalog_has_expected_components():
    catalog = load_catalog("0.8")
    names = {c["name"] for c in catalog["components"]}
    assert {"DefectResultsTable", "DefectRow", "SeverityBadge",
            "SeverityBreakdownChoicePicker"}.issubset(names)


def test_extract_a2ui_surface_from_fenced_response():
    surface = extract_a2ui_surface(SAMPLE_AGENT_RESPONSE)
    assert surface is not None
    assert surface["component"] == "DefectResultsTable"
    assert surface["rows"][0]["defect_id"] == "DEF-100482"


def test_build_inline_a2ui_data_parts():
    surface = extract_a2ui_surface(SAMPLE_AGENT_RESPONSE)
    parts = build_a2ui_data_parts(surface, use_decoupled_pattern=False)
    types_seen = [p["data"]["type"] for p in parts]
    assert types_seen == ["beginRendering", "surfaceUpdate"]
    assert all(p["mimeType"] == "application/json+a2ui" for p in parts)


def test_build_decoupled_a2ui_data_parts():
    surface = extract_a2ui_surface(SAMPLE_AGENT_RESPONSE)
    parts = build_a2ui_data_parts(surface, use_decoupled_pattern=True)
    types_seen = [p["data"]["type"] for p in parts]
    assert types_seen == ["createSurface", "updateDataModel", "updateComponents"]


def test_unknown_component_is_rejected():
    bad_surface = {"component": "NotInCatalog", "rows": []}
    try:
        build_a2ui_data_parts(bad_surface)
        assert False, "expected ValueError for unknown component"
    except ValueError:
        pass


def test_sql_guardrail_rejects_non_select():
    try:
        _validate_select_only(
            "DELETE FROM `p.aerospace_quality.aircraft_defects` WHERE 1=1"
        )
        assert False, "expected BigQueryToolError"
    except BigQueryToolError:
        pass


def test_sql_guardrail_allows_scoped_select(monkeypatch):
    monkeypatch.setenv("BIGQUERY_PROJECT_ID", "p")
    monkeypatch.setenv("BIGQUERY_DATASET", "aerospace_quality")
    monkeypatch.setenv("BIGQUERY_TABLE", "aircraft_defects")
    import importlib
    import app.tools.bigquery_live_query as bq_module
    importlib.reload(bq_module)
    bq_module._validate_select_only(
        "SELECT severity_level, COUNT(*) FROM `p.aerospace_quality.aircraft_defects` "
        "GROUP BY severity_level"
    )


if __name__ == "__main__":
    test_load_catalog_has_expected_components()
    test_extract_a2ui_surface_from_fenced_response()
    test_build_inline_a2ui_data_parts()
    test_build_decoupled_a2ui_data_parts()
    test_unknown_component_is_rejected()
    test_sql_guardrail_rejects_non_select()
    print("All smoke tests passed.")
