"""Latency percentile distribution — runs N sequential requests and reports p50/p90/p99."""

import logging
import statistics
import time
from dataclasses import dataclass, field

from openai import OpenAI

logger = logging.getLogger(__name__)

_PERCENTILE_PROMPT = "What is the capital of France? Answer in one word."
_SAMPLE_COUNT = 20


@dataclass
class PercentilesResult:
    p50_ms: float
    p90_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    std_ms: float
    sample_count: int       # successful samples
    failed_count: int
    success: bool
    error: str | None = None
    raw_latencies_ms: list[float] = field(default_factory=list, repr=False)


def measure_percentiles(
    client: OpenAI,
    model: str,
    prompt: str = _PERCENTILE_PROMPT,
    max_tokens: int = 32,
    sample_count: int = _SAMPLE_COUNT,
) -> PercentilesResult:
    """
    Fire `sample_count` sequential non-streaming requests and compute
    the full latency distribution.  Uses a very short prompt so the
    test completes quickly and the distribution reflects serving latency
    rather than generation time.
    """
    latencies_ms: list[float] = []
    failed = 0

    for i in range(sample_count):
        try:
            t0 = time.perf_counter()
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                stream=False,
            )
            latencies_ms.append((time.perf_counter() - t0) * 1000)
        except Exception as exc:
            failed += 1
            logger.warning("Percentile sample %d/%d failed: %s", i + 1, sample_count, exc)

    if not latencies_ms:
        return PercentilesResult(
            p50_ms=0.0, p90_ms=0.0, p99_ms=0.0,
            mean_ms=0.0, min_ms=0.0, max_ms=0.0, std_ms=0.0,
            sample_count=0, failed_count=failed,
            success=False, error=f"All {sample_count} samples failed",
        )

    s = sorted(latencies_ms)
    n = len(s)

    result = PercentilesResult(
        p50_ms=s[int(n * 0.50)],
        p90_ms=s[min(int(n * 0.90), n - 1)],
        p99_ms=s[min(int(n * 0.99), n - 1)],
        mean_ms=statistics.mean(latencies_ms),
        min_ms=s[0],
        max_ms=s[-1],
        std_ms=statistics.stdev(latencies_ms) if n > 1 else 0.0,
        sample_count=n,
        failed_count=failed,
        success=True,
        raw_latencies_ms=latencies_ms,
    )
    logger.debug(
        "Percentiles (%d samples): p50=%.0fms p90=%.0fms p99=%.0fms",
        n, result.p50_ms, result.p90_ms, result.p99_ms,
    )
    return result
