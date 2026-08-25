.PHONY: install playground local-backend deploy-agent-engine setup-auth-provider setup-bigquery-connector register-gemini-enterprise test lint

install:
	uv sync

# Launches the ADK development playground (`adk web`) for the root agent,
# useful for exercising the 3-legged OAuth consent flow locally before
# deploying, per https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2#frontend-and-user-consent-implementation
playground:
	uv run adk web app

# Runs the A2A server locally (app/main.py) so Gemini Enterprise or the
# optional Lit shell can call it during development.
local-backend:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# One-time: creates the 3-legged OAuth Agent Identity auth provider for the
# BigQuery connector, per https://docs.cloud.google.com/iam/docs/auth-with-3lo-v2
setup-auth-provider:
	bash deployment/setup_auth_provider.sh

# One-time: creates (or points at) the Gemini Enterprise Data Store fed by
# the BigQuery connector, per
# https://docs.cloud.google.com/gemini/enterprise/docs/connectors/connect-bigquery
setup-bigquery-connector:
	bash deployment/setup_bigquery_connector.sh

# Deploys the agent to Vertex AI Agent Engine with Agent Identity enabled.
deploy-agent-engine:
	uv run python deployment/deploy_agent_engine.py

# Registers this agent's A2A endpoint with Gemini Enterprise, per
# https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
register-gemini-enterprise:
	bash deployment/register_gemini_enterprise.sh

test:
	uv run pytest tests -q

lint:
	uv run python -m py_compile $$(find app deployment -name "*.py")
