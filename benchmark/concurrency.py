"""Concurrency sweep — runs the same workload at increasing parallelism levels."""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field

from openai import OpenAI

logger = logging.getLogger(__name__)

CONCURRENCY_LEVELS  = [1, 5, 10, 25, 50]
REQUESTS_PER_LEVEL  = 10      # kept small to avoid excessive cost
_PROMPT             = "List three facts about the ocean."


@dataclass
class ConcurrencyLevelResult:
    concurrency:         int
    requests_per_second: float
    latency_p95_ms:      float
    latency_mean_ms:     float
    success_rate:        float
    total_tokens:        int
    duration_s:          float
    success:             bool


@dataclass
class ConcurrencyResults:
    levels:  list[ConcurrencyLevelResult] = field(default_factory=list)
    success: bool = True
    error:   str | None = None


def _single(client: OpenAI, model: str, prompt: str, max_tokens: int) -> tuple[bool, float, int]:
    """Returns (ok, latency_ms, output_tokens)."""
    try:
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            stream=False,
        )
        lat = (time.perf_counter() - t0) * 1000
        tok = resp.usage.completion_tokens if resp.usage else 0
        return True, lat, tok
    except Exception as exc:
        logger.warning("Concurrency request failed: %s", exc)
        return False, 0.0, 0


def _run_level(
    client: OpenAI,
    model: str,
    concurrency: int,
    n_requests: int,
    prompt: str,
    max_tokens: int,
) -> ConcurrencyLevelResult:
    latencies: list[float] = []
    tokens_total = 0
    failures = 0
    t_start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(_single, client, model, prompt, max_tokens)
            for _ in range(n_requests)
        ]
        for fut in concurrent.futures.as_completed(futures):
            ok, lat, tok = fut.result()
            if ok:
                latencies.append(lat)
                tokens_total += tok
            else:
                failures += 1

    duration = time.perf_counter() - t_start
    successes = len(latencies)
    rps = successes / duration if duration > 0 else 0.0
    sr  = successes / n_requests if n_requests > 0 else 0.0

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p95 = sorted_lat[min(int(n * 0.95), n - 1)] if n else 0.0
    mean = sum(latencies) / n if n else 0.0

    logger.info(
        "Concurrency=%d: %.2f rps  p95=%.0fms  sr=%.0f%%",
        concurrency, rps, p95, sr * 100,
    )

    return ConcurrencyLevelResult(
        concurrency=concurrency,
        requests_per_second=rps,
        latency_p95_ms=p95,
        latency_mean_ms=mean,
        success_rate=sr,
        total_tokens=tokens_total,
        duration_s=duration,
        success=successes > 0,
    )


def run_concurrency_sweep(
    client: OpenAI,
    model: str,
    levels: list[int] = CONCURRENCY_LEVELS,
    requests_per_level: int = REQUESTS_PER_LEVEL,
    prompt: str = _PROMPT,
    max_tokens: int = 64,
    on_progress: callable = None,
) -> ConcurrencyResults:
    """Run the workload at each concurrency level sequentially."""
    results: list[ConcurrencyLevelResult] = []

    for c in levels:
        if on_progress:
            on_progress(f"Concurrency {c} ({requests_per_level} requests)…")
        try:
            lvl = _run_level(client, model, c, requests_per_level, prompt, max_tokens)
            results.append(lvl)
        except Exception as exc:
            logger.error("Concurrency level %d failed: %s", c, exc)
            results.append(ConcurrencyLevelResult(
                concurrency=c, requests_per_second=0, latency_p95_ms=0,
                latency_mean_ms=0, success_rate=0, total_tokens=0,
                duration_s=0, success=False,
            ))

    return ConcurrencyResults(levels=results, success=True)
