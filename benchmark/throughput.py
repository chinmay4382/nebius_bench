import concurrent.futures
import logging
import time
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)

_THROUGHPUT_PROMPT = "List three facts about the moon."
_NUM_REQUESTS = 10
_MAX_WORKERS  = 5


@dataclass
class ThroughputResult:
    requests_per_second: float
    tokens_per_second: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_output_tokens: int
    total_duration_seconds: float
    success_rate: float


def _execute_single(
    client: OpenAI, model: str, prompt: str, max_tokens: int
) -> tuple[bool, int]:
    """Returns (success, output_token_count)."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            stream=False,
        )
        tokens = resp.usage.completion_tokens if resp.usage else 0
        return True, tokens
    except Exception as exc:
        logger.warning("Throughput request failed: %s", exc)
        return False, 0


def measure_throughput(
    client: OpenAI,
    model: str,
    prompt: str = _THROUGHPUT_PROMPT,
    num_requests: int = _NUM_REQUESTS,
    max_workers: int = _MAX_WORKERS,
    max_tokens: int = 64,
) -> ThroughputResult:
    """Send num_requests concurrent requests; measure RPS and token throughput."""
    logger.info("Throughput test: %d requests / %d workers", num_requests, max_workers)

    successes      = 0
    failures       = 0
    total_tokens   = 0
    start_time     = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_execute_single, client, model, prompt, max_tokens)
            for _ in range(num_requests)
        ]
        for future in concurrent.futures.as_completed(futures):
            ok, tok = future.result()
            if ok:
                successes    += 1
                total_tokens += tok
            else:
                failures += 1

    total_duration = time.perf_counter() - start_time
    rps   = successes    / total_duration if total_duration > 0 else 0.0
    tps   = total_tokens / total_duration if total_duration > 0 else 0.0
    sr    = successes    / num_requests   if num_requests   > 0 else 0.0

    logger.info(
        "Throughput: %.2f rps  %.1f tok/s  %d/%d ok  %.1fs",
        rps, tps, successes, num_requests, total_duration,
    )

    return ThroughputResult(
        requests_per_second=rps,
        tokens_per_second=tps,
        total_requests=num_requests,
        successful_requests=successes,
        failed_requests=failures,
        total_output_tokens=total_tokens,
        total_duration_seconds=total_duration,
        success_rate=sr,
    )
