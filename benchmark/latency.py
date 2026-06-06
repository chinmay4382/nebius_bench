import logging
import time
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)

_LATENCY_PROMPT = "What is the capital of France? Answer in one word."


@dataclass
class LatencyResult:
    latency_ms: float
    token_count: int
    tokens_per_second: float
    success: bool
    error: str | None = None


def measure_latency(
    client: OpenAI,
    model: str,
    prompt: str = _LATENCY_PROMPT,
    max_tokens: int = 64,
) -> LatencyResult:
    """Measure end-to-end latency for a non-streaming request."""
    request_start = time.perf_counter()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            stream=False,
        )

        latency_ms = (time.perf_counter() - request_start) * 1000
        token_count = response.usage.completion_tokens if response.usage else 0
        tps = (token_count / (latency_ms / 1000)) if latency_ms > 0 and token_count > 0 else 0.0

        logger.debug("Latency: %.1fms  tokens: %d  tps: %.1f", latency_ms, token_count, tps)
        return LatencyResult(
            latency_ms=latency_ms,
            token_count=token_count,
            tokens_per_second=tps,
            success=True,
        )

    except Exception as exc:
        logger.error("Latency measurement failed: %s", exc)
        return LatencyResult(
            latency_ms=0.0, token_count=0, tokens_per_second=0.0,
            success=False, error=str(exc),
        )
