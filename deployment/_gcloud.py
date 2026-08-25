"""Small cross-platform helper for shelling out to `gcloud`.

Used by the other deployment scripts so they run identically on Windows,
macOS, and Linux -- no bash-only syntax anywhere in this repo. On Windows,
`gcloud` is installed as a `.cmd` shim, which `subprocess` can only resolve
when `shell=True`; on POSIX this is a no-op equivalent to a normal exec.
"""

from __future__ import annotations

import os
import subprocess
import sys


def run_gcloud(args: list[str], capture: bool = True) -> str:
    """Runs `gcloud <args>` and returns stdout (stripped). Raises
    SystemExit with a readable message on failure instead of a raw
    traceback, since these scripts are meant to be run interactively."""
    cmd = ["gcloud", *args]
    try:
        result = subprocess.run(
            cmd,
            shell=(os.name == "nt"),
            capture_output=capture,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit(
            "gcloud CLI not found on PATH. Install it from "
            "https://cloud.google.com/sdk/docs/install (Windows installer "
            "available) and run `gcloud init` first."
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(f"gcloud command failed ({' '.join(cmd)}):\n{exc.stderr or exc.stdout}")
    return (result.stdout or "").strip() if capture else ""


def access_token() -> str:
    return run_gcloud(["auth", "print-access-token"])


def project_number(project_id: str) -> str:
    return run_gcloud(
        ["projects", "describe", project_id, "--format=value(projectNumber)"]
    )


def current_account() -> str:
    return run_gcloud(["config", "get-value", "account"])
