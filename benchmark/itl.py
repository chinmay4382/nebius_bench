"""Inter-Token Latency (ITL) — measures the gap between consecutive streamed tokens."""

import logging
import statistics
import time
from dataclasses import dataclass, field

from openai import OpenAI

logger = logging.getLogger(__name__)

_ITL_PROMPT = (
    "Explain in detail how transformer attention mechanisms work, "
    "covering self-attention, multi-head attention, and positional encoding."
)


@dataclass
class ITLResult:
    mean_itl_ms: float
    p50_itl_ms: float
    p90_itl_ms: float
    p99_itl_ms: float
    tokens_per_second: float
    token_count: int
    success: bool
    error: str | None = None
    raw_gaps_ms: list[float] = field(default_factory=list, repr=False)


def measure_itl(
    client: OpenAI,
    model: str,
    prompt: str = _ITL_PROMPT,
    max_tokens: int = 300,
) -> ITLResult:
    """
    Stream a single response and record the wall-clock time between
    each consecutive token chunk.  Reports mean / p50 / p90 / p99 ITL
    and the effective tokens-per-second generation rate.
    """
    token_timestamps: list[float] = []

    try:
        stream_start = time.perf_counter()

        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token_timestamps.append(time.perf_counter())

        stream.close()

        if len(token_timestamps) < 2:
            return ITLResult(
                mean_itl_ms=0.0, p50_itl_ms=0.0, p90_itl_ms=0.0, p99_itl_ms=0.0,
                tokens_per_second=0.0, token_count=len(token_timestamps),
                success=False, error="Too few tokens received to compute ITL",
            )

        gaps_ms = [
            (token_timestamps[i] - token_timestamps[i - 1]) * 1000
            for i in range(1, len(token_timestamps))
        ]
        gaps_sorted = sorted(gaps_ms)
        n = len(gaps_sorted)

        total_s = token_timestamps[-1] - stream_start
        tps = len(token_timestamps) / total_s if total_s > 0 else 0.0

        result = ITLResult(
            mean_itl_ms=statistics.mean(gaps_ms),
            p50_itl_ms=gaps_sorted[int(n * 0.50)],
            p90_itl_ms=gaps_sorted[min(int(n * 0.90), n - 1)],
            p99_itl_ms=gaps_sorted[min(int(n * 0.99), n - 1)],
            tokens_per_second=tps,
            token_count=len(token_timestamps),
            success=True,
            raw_gaps_ms=gaps_ms,
        )
        logger.debug(
            "ITL: mean=%.1fms p90=%.1fms tps=%.1f tokens=%d",
            result.mean_itl_ms, result.p90_itl_ms, result.tokens_per_second, result.token_count,
        )
        return result

    except Exception as exc:
        logger.error("ITL measurement failed: %s", exc)
        return ITLResult(
            mean_itl_ms=0.0, p50_itl_ms=0.0, p90_itl_ms=0.0, p99_itl_ms=0.0,
            tokens_per_second=0.0, token_count=0, success=False, error=str(exc),
        )
