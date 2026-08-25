"""Turns the agent's `a2ui_surface` JSON convention into real A2UI protocol
messages, transported as A2A `DataPart` objects with MIME type
`application/json+a2ui`, following the pattern described in
https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
and implemented in https://github.com/wadave/agent-a2ui-demo
(`app/agent_executor.py`).

Two message patterns are supported, negotiated by the calling client's
`X-A2A-Extensions` header (`app/agent_executor.py` reads the header and picks
the pattern):

- **Inline pattern** (`beginRendering` + `surfaceUpdate`, data embedded
  directly in the component): this is what Gemini Enterprise renders today.
- **Decoupled pattern** (`createSurface` + `updateDataModel` +
  `updateComponents`, sent as separate messages): used by the custom Lit
  reference shell; keeps the door open for future re-use of a data model
  across turns.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

A2UI_MIME_TYPE = "application/json+a2ui"

_CATALOG_DIR = Path(__file__).resolve().parent.parent / "catalog_schemas"

_SURFACE_ID_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def load_catalog(version: str = "0.8") -> dict[str, Any]:
    """Loads the aerospace defect A2UI catalog for the given version."""
    catalog_path = _CATALOG_DIR / version / "aerospace_defect_catalog.json"
    with catalog_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def extract_a2ui_surface(agent_final_text: str) -> dict[str, Any] | None:
    """Pulls the `a2ui_surface` JSON object out of the agent's final answer.

    The root-agent instruction (see `app/prompts.py`) asks the model to
    return a fenced ```json block (or a bare JSON object) containing an
    `a2ui_surface` key whenever it has a defect result set to render. This
    helper is intentionally forgiving about surrounding prose so the
    natural-language summary and the structured surface can share one
    model response.
    """
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", agent_final_text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(agent_final_text)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and "a2ui_surface" in parsed:
            return parsed["a2ui_surface"]
        if isinstance(parsed, dict) and "component" in parsed:
            return parsed
    return None


def _new_surface_id(component_name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", component_name.lower())
    surface_id = f"{slug}-{uuid.uuid4().hex[:8]}"
    assert _SURFACE_ID_RE.match(surface_id)
    return surface_id


def _validate_against_catalog(surface: dict[str, Any], catalog: dict[str, Any]) -> None:
    component_names = {c["name"] for c in catalog.get("components", [])}
    component = surface.get("component")
    if component not in component_names:
        raise ValueError(
            f"A2UI surface references unknown component '{component}'. "
            f"Known components: {sorted(component_names)}"
        )


def build_inline_messages(
    surface: dict[str, Any], catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    """Builds the Gemini Enterprise v0.8 inline pattern:
    `beginRendering` followed by `surfaceUpdate` with data embedded inline
    in the component payload.
    """
    _validate_against_catalog(surface, catalog)
    surface_id = _new_surface_id(surface["component"])
    component = {k: v for k, v in surface.items() if k != "component"}
    return [
        {
            "type": "beginRendering",
            "surfaceId": surface_id,
            "catalogId": catalog["catalogId"],
            "rootComponent": surface["component"],
        },
        {
            "type": "surfaceUpdate",
            "surfaceId": surface_id,
            "component": surface["component"],
            "data": component,
        },
    ]


def build_decoupled_messages(
    surface: dict[str, Any], catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    """Builds the v0.9 decoupled pattern used by the custom Lit reference
    shell: `createSurface` -> `updateDataModel` -> `updateComponents`,
    allowing the data model to be reused/updated independently of the
    component tree on later turns.
    """
    _validate_against_catalog(surface, catalog)
    surface_id = _new_surface_id(surface["component"])
    component = {k: v for k, v in surface.items() if k != "component"}
    return [
        {
            "type": "createSurface",
            "surfaceId": surface_id,
            "catalogId": catalog["catalogId"],
        },
        {
            "type": "updateDataModel",
            "surfaceId": surface_id,
            "data": component,
        },
        {
            "type": "updateComponents",
            "surfaceId": surface_id,
            "rootComponent": surface["component"],
        },
    ]


def build_a2ui_data_parts(
    surface: dict[str, Any],
    catalog_version: str = "0.8",
    use_decoupled_pattern: bool = False,
) -> list[dict[str, Any]]:
    """Builds A2A `DataPart`-ready dicts (mimeType + data) carrying the A2UI
    protocol messages for the given surface.

    `use_decoupled_pattern` is normally decided by `agent_executor.py` from
    the request's `X-A2A-Extensions` header — Gemini Enterprise omits the
    header (inline pattern, v0.8) while the custom Lit shell requests v0.9
    (decoupled pattern).
    """
    catalog = load_catalog(catalog_version)
    messages = (
        build_decoupled_messages(surface, catalog)
        if use_decoupled_pattern
        else build_inline_messages(surface, catalog)
    )
    return [{"mimeType": A2UI_MIME_TYPE, "data": message} for message in messages]
