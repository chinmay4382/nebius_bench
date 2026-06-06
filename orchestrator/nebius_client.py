import json
import logging
import os
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# Standard Nebius CLI install paths (appended to PATH at runtime if needed)
_NEBIUS_SEARCH_PATHS = [
    os.path.expanduser("~/.nebius/bin"),
    "/usr/local/bin",
    "/usr/bin",
]


def _resolve_nebius_binary() -> str:
    """Return path to the nebius binary, searching standard install locations."""
    binary = shutil.which("nebius")
    if binary:
        return binary
    for directory in _NEBIUS_SEARCH_PATHS:
        candidate = os.path.join(directory, "nebius")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise NebiusClientError(
        "Nebius CLI not found. Install it from https://nebius.com/docs/cli/quickstart\n"
        "Then ensure it is on your PATH or at ~/.nebius/bin/nebius"
    )


class NebiusClientError(Exception):
    pass


def run_nebius_command(args: list[str], timeout: int = 60) -> dict[str, Any]:
    """Execute a nebius CLI command and return parsed JSON output."""
    binary = _resolve_nebius_binary()
    cmd = [binary] + args + ["--format", "json", "--no-progress"]

    profile = os.getenv("NEBIUS_PROFILE")
    if profile:
        cmd.extend(["--profile", profile])

    logger.debug("Executing: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise NebiusClientError(
                f"Nebius CLI error (exit {result.returncode}): {result.stderr.strip()}"
            )

        output = result.stdout.strip()
        if not output:
            return {}

        return json.loads(output)

    except subprocess.TimeoutExpired:
        raise NebiusClientError(f"Nebius CLI command timed out after {timeout}s")
    except json.JSONDecodeError as exc:
        raise NebiusClientError(
            f"Failed to parse Nebius CLI output as JSON: {exc}\nRaw: {result.stdout[:500]}"
        )
    except FileNotFoundError:
        raise NebiusClientError(
            "Nebius CLI not found. Install it from https://nebius.com/docs/cli/quickstart\n"
            "Then ensure it is on your PATH or at ~/.nebius/bin/nebius"
        )
