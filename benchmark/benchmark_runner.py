import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

from openai import OpenAI

from .itl import ITLResult, measure_itl
from .latency import LatencyResult, measure_latency
from .percentiles import PercentilesResult, measure_percentiles
from .throughput import ThroughputResult, measure_throughput
from .ttft import TTFTResult, measure_ttft

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResults:
    model: str
    endpoint_url: str
    ttft: TTFTResult
    itl: ITLResult
    latency: LatencyResult
    percentiles: PercentilesResult
    throughput: ThroughputResult


def run_benchmark(
    endpoint_url: str,
    model: str,
    max_tokens: int = 512,
    auth_token: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> BenchmarkResults:
    """Run the full benchmark suite against a running Nebius endpoint."""
    api_key  = auth_token or os.getenv("NEBIUS_API_KEY") or "dummy"
    base_url = endpoint_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=180.0)
    logger.info("Benchmark start: model=%s url=%s", model, base_url)

    def _prog(msg: str) -> None:
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    _prog("Measuring TTFT (streaming)…")
    ttft = measure_ttft(client, model, max_tokens=max_tokens)
    # Retry once on transient timeout
    if not ttft.success and ttft.error and "timed out" in (ttft.error or "").lower():
        _prog("TTFT timed out, retrying…")
        ttft = measure_ttft(client, model, max_tokens=max_tokens)

    _prog("Measuring Inter-Token Latency (ITL)…")
    itl = measure_itl(client, model, max_tokens=min(300, max_tokens))

    _prog("Measuring end-to-end latency…")
    latency = measure_latency(client, model, max_tokens=min(64, max_tokens))

    _prog("Measuring latency percentiles (20 samples)…")
    percentiles = measure_percentiles(client, model, max_tokens=min(32, max_tokens))

    _prog("Measuring throughput (10 concurrent requests)…")
    throughput = measure_throughput(client, model, max_tokens=min(64, max_tokens))

    logger.info(
        "Benchmark complete — TTFT=%.0fms ITL=%.1fms p90=%.0fms "
        "latency=%.0fms rps=%.2f tok/s=%.1f success=%.0f%%",
        ttft.ttft_ms,
        itl.mean_itl_ms,
        percentiles.p90_ms,
        latency.latency_ms,
        throughput.requests_per_second,
        throughput.tokens_per_second,
        throughput.success_rate * 100,
    )

    return BenchmarkResults(
        model=model,
        endpoint_url=endpoint_url,
        ttft=ttft,
        itl=itl,
        latency=latency,
        percentiles=percentiles,
        throughput=throughput,
    )
