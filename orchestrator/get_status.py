import logging
import re
from dataclasses import dataclass
from enum import Enum

from .nebius_client import run_nebius_command

logger = logging.getLogger(__name__)


class EndpointState(str, Enum):
    CREATING = "CREATING"
    PROVISIONING = "PROVISIONING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    ERROR = "ERROR"        # vLLM / container crash after VM is up
    UNKNOWN = "UNKNOWN"

    @property
    def is_terminal_ok(self) -> bool:
        return self == EndpointState.RUNNING

    @property
    def is_terminal_fail(self) -> bool:
        return self in (EndpointState.FAILED, EndpointState.ERROR)

    @property
    def is_transient(self) -> bool:
        return self in (
            EndpointState.CREATING,
            EndpointState.PROVISIONING,
            EndpointState.STARTING,
        )


@dataclass
class EndpointStatus:
    endpoint_id: str
    state: EndpointState
    url: str | None
    auth_token: str | None
    model: str | None
    error: str | None = None


def _extract_url(response: dict) -> str | None:
    public_eps = response.get("status", {}).get("public_endpoints", [])
    if public_eps:
        host_port = public_eps[0]
        return f"http://{host_port}"

    private_eps = response.get("status", {}).get("private_endpoints", [])
    if private_eps:
        host_port = private_eps[0]
        return f"http://{host_port}"

    return None


def _extract_model(response: dict) -> str | None:
    args_str = response.get("spec", {}).get("args", "")
    if not args_str:
        return None

    served = re.search(r"--served-model-name\s+(\S+)", args_str)
    if served:
        return served.group(1)

    model = re.search(r"--model\s+(\S+)", args_str)
    if model:
        return model.group(1)

    return None


def get_endpoint_status(endpoint_id: str) -> EndpointStatus:
    """Return the current status of a Nebius AI endpoint."""
    response = run_nebius_command(["ai", "endpoint", "get", "--id", endpoint_id])

    state_str = response.get("status", {}).get("state", "UNKNOWN").upper()
    try:
        state = EndpointState(state_str)
    except ValueError:
        logger.warning("Unrecognised endpoint state %r, treating as UNKNOWN", state_str)
        state = EndpointState.UNKNOWN

    url = _extract_url(response)
    auth_token = response.get("spec", {}).get("auth_token")
    model = _extract_model(response)

    error: str | None = None
    if state == EndpointState.FAILED:
        error = response.get("status", {}).get("error") or "Unknown failure reason"

    logger.debug("Endpoint %s: state=%s url=%s", endpoint_id, state, url)

    return EndpointStatus(
        endpoint_id=endpoint_id,
        state=state,
        url=url,
        auth_token=auth_token,
        model=model,
        error=error,
    )
