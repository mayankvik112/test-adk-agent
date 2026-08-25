# Container image for deploying app/main.py (the A2A endpoint) to Cloud Run
# or GKE, per the "A2A endpoint can run on Cloud Run, GKE, or on-premises
# infrastructure" deployment shape described in
# https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration
#
# Built with uv (https://docs.astral.sh/uv/guides/integration/docker/) for
# fast, reproducible, lockfile-pinned installs. Works identically on
# Windows (Docker Desktop, WSL2 backend), macOS, and Linux -- the image
# itself is always Linux, so there is no bash/PowerShell dependency here.
FROM python:3.11-slim

# Pin the official static uv binary instead of `pip install uv`, per the
# uv Docker integration guide above.
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies first (cached separately from source changes).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Now copy source and install the project itself.
COPY app ./app
COPY deployment ./deployment
RUN uv sync --frozen --no-dev

ENV PORT=8080
EXPOSE 8080

# `uv run` resolves the synced /app/.venv automatically -- no manual
# `source .venv/bin/activate` / PATH juggling needed.
CMD ["uv", "run", "python", "-m", "app.main"]
