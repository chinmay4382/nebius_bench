import logging
import time
from collections.abc import Callable

from .get_status import EndpointState, EndpointStatus, get_endpoint_status
from .nebius_client import NebiusClientError

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes


def wait_until_ready(
    endpoint_id: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    on_status_update: Callable[[EndpointStatus, float], None] | None = None,
) -> tuple[EndpointStatus, float]:
    """
    Poll endpoint until RUNNING (ready) or FAILED.

    Returns (final_status, elapsed_seconds).
    Raises TimeoutError if the endpoint does not become ready within timeout_seconds.
    Raises RuntimeError if the endpoint enters a FAILED state.
    """
    start_time = time.time()
    last_state: EndpointState | None = None
    consecutive_errors = 0

    while True:
        elapsed = time.time() - start_time

        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Endpoint {endpoint_id} did not become RUNNING within {timeout_seconds:.0f}s"
            )

        try:
            status = get_endpoint_status(endpoint_id)
            consecutive_errors = 0
        except NebiusClientError as exc:
            consecutive_errors += 1
            logger.warning(
                "Status poll error #%d for %s: %s",
                consecutive_errors,
                endpoint_id,
                exc,
            )
            if consecutive_errors >= 5:
                raise RuntimeError(
                    f"Too many consecutive poll errors for {endpoint_id}: {exc}"
                ) from exc
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if status.state != last_state:
            logger.info(
                "Endpoint %s transitioned to %s (elapsed %.0fs)",
                endpoint_id,
                status.state,
                elapsed,
            )
            last_state = status.state

        if on_status_update is not None:
            on_status_update(status, elapsed)

        if status.state.is_terminal_ok:
            logger.info("Endpoint %s is RUNNING after %.0fs", endpoint_id, elapsed)
            return status, elapsed

        if status.state.is_terminal_fail:
            raise RuntimeError(
                f"Endpoint {endpoint_id} failed: {status.error or 'unknown error'}"
            )

        time.sleep(POLL_INTERVAL_SECONDS)
