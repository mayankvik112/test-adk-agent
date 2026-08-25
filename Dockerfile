# Container image for deploying app/main.py (the A2A endpoint) to Cloud Run
# or GKE, per the "A2A endpoint can run on Cloud Run, GKE, or on-premises
# infrastructure" deployment shape described in
# https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY app ./app
COPY deployment ./deployment

RUN uv sync --no-dev || uv pip install --system \
    "google-cloud-aiplatform[agent_engines,adk]>=1.85.0" \
    "google-adk[agent-identity,mcp,a2a]>=2.7.1" \
    "a2a-sdk>=0.2.0" "uvicorn>=0.30.0" "httpx>=0.27.0" "google-auth>=2.30.0"

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "app.main"]
