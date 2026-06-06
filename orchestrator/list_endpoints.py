import logging
import re
from dataclasses import dataclass

from .get_status import EndpointState
from .nebius_client import run_nebius_command

logger = logging.getLogger(__name__)


@dataclass
class EndpointInfo:
    endpoint_id: str
    name: str
    state: EndpointState
    model: str | None
    url: str | None
    auth_token: str | None
    platform: str | None
    preset: str | None
    image: str | None
    created_at: str | None


def _parse_one(item: dict) -> EndpointInfo:
    meta   = item.get("metadata", {})
    spec   = item.get("spec", {})
    status = item.get("status", {})

    state_str = status.get("state", "UNKNOWN").upper()
    try:
        state = EndpointState(state_str)
    except ValueError:
        state = EndpointState.UNKNOWN

    # URL from public endpoints
    public_eps = status.get("public_endpoints", [])
    url = f"http://{public_eps[0]}" if public_eps else None

    # Model from vLLM args
    args = spec.get("args", "")
    model: str | None = None
    served = re.search(r"--served-model-name\s+(\S+)", args)
    if served:
        model = served.group(1)
    else:
        m = re.search(r"--model\s+(\S+)", args)
        if m:
            model = m.group(1)

    return EndpointInfo(
        endpoint_id = meta.get("id", ""),
        name        = meta.get("name", ""),
        state       = state,
        model       = model,
        url         = url,
        auth_token  = spec.get("auth_token"),
        platform    = spec.get("platform"),
        preset      = spec.get("preset"),
        image       = spec.get("image"),
        created_at  = meta.get("created_at"),
    )


def list_endpoints() -> list[EndpointInfo]:
    """Return all Nebius AI endpoints for the active project."""
    response = run_nebius_command(["ai", "endpoint", "list"])
    items = response.get("items", [])
    logger.info("Found %d endpoint(s)", len(items))
    return [_parse_one(i) for i in items]
