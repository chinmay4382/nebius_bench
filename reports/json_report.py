import json
import time

from benchmark.benchmark_runner import BenchmarkResults


def generate_json_report(
    model: str,
    benchmark_results: BenchmarkResults,
    endpoint_creation_time_seconds: float,
    time_to_ready_seconds: float,
    deletion_time_seconds: float | None = None,
) -> str:
    r = benchmark_results
    report: dict = {
        "model":                         model,
        "timestamp":                     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint_creation_time_seconds": round(endpoint_creation_time_seconds, 2),
        "time_to_ready_seconds":          round(time_to_ready_seconds, 2),

        "ttft_ms":                        round(r.ttft.ttft_ms, 2),

        "itl_mean_ms":                    round(r.itl.mean_itl_ms, 2),
        "itl_p50_ms":                     round(r.itl.p50_itl_ms, 2),
        "itl_p90_ms":                     round(r.itl.p90_itl_ms, 2),
        "itl_p99_ms":                     round(r.itl.p99_itl_ms, 2),
        "itl_tokens_per_second":          round(r.itl.tokens_per_second, 2),
        "itl_token_count":                r.itl.token_count,

        "latency_ms":                     round(r.latency.latency_ms, 2),
        "latency_tokens_per_second":      round(r.latency.tokens_per_second, 2),

        "latency_p50_ms":                 round(r.percentiles.p50_ms, 2),
        "latency_p90_ms":                 round(r.percentiles.p90_ms, 2),
        "latency_p99_ms":                 round(r.percentiles.p99_ms, 2),
        "latency_mean_ms":                round(r.percentiles.mean_ms, 2),
        "latency_min_ms":                 round(r.percentiles.min_ms, 2),
        "latency_max_ms":                 round(r.percentiles.max_ms, 2),
        "latency_std_ms":                 round(r.percentiles.std_ms, 2),
        "latency_sample_count":           r.percentiles.sample_count,

        "requests_per_second":            round(r.throughput.requests_per_second, 3),
        "throughput_tokens_per_second":   round(r.throughput.tokens_per_second, 2),
        "total_output_tokens":            r.throughput.total_output_tokens,
        "success_rate":                   round(r.throughput.success_rate, 4),
        "total_requests":                 r.throughput.total_requests,
        "successful_requests":            r.throughput.successful_requests,
        "failed_requests":                r.throughput.failed_requests,
    }

    if deletion_time_seconds is not None:
        report["deletion_time_seconds"] = round(deletion_time_seconds, 2)

    return json.dumps(report, indent=2)
