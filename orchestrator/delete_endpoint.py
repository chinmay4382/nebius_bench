import logging
import time
from dataclasses import dataclass

from .nebius_client import run_nebius_command

logger = logging.getLogger(__name__)


@dataclass
class DeletionResult:
    endpoint_id: str
    deletion_duration_seconds: float
    success: bool


def delete_endpoint(endpoint_id: str) -> DeletionResult:
    """Delete a Nebius AI endpoint and return timing details."""
    start_time = time.time()
    logger.info("Deleting endpoint: %s", endpoint_id)

    run_nebius_command(["ai", "endpoint", "delete", "--id", endpoint_id], timeout=60)

    duration = time.time() - start_time
    logger.info("Endpoint %s deleted in %.1fs", endpoint_id, duration)

    return DeletionResult(
        endpoint_id=endpoint_id,
        deletion_duration_seconds=duration,
        success=True,
    )
