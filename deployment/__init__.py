"""Deployment / provisioning scripts for the Aerospace Quality & Reliability
Intelligence agent. Run these as modules from the repo root so relative
imports and the `app` package both resolve correctly on every OS, e.g.:

    uv run python -m deployment.setup_bigquery_connector
    uv run python -m deployment.setup_auth_provider
    uv run python -m deployment.register_gemini_enterprise
    uv run python -m deployment.deploy_agent_engine
"""
