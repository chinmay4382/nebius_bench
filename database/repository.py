"""Repository layer — all DB access goes through this class."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from .models import (
    BenchmarkRun,
    ConcurrencyResult,
    DeploymentMetrics,
    PerformanceMetrics,
    RunMeta,
)


# ── Transfer objects ────────────────────────────────────────────────────────────

@dataclass
class DeploymentRecord:
    endpoint_creation_time_s: float | None = None
    time_to_ready_s:          float | None = None
    deletion_time_s:          float | None = None


@dataclass
class PerformanceRecord:
    ttft_ms:                       float | None = None
    itl_mean_ms:                   float | None = None
    itl_p50_ms:                    float | None = None
    itl_p90_ms:                    float | None = None
    itl_p99_ms:                    float | None = None
    itl_tokens_per_second:         float | None = None
    latency_ms:                    float | None = None
    latency_tokens_per_second:     float | None = None
    lat_p50_ms:                    float | None = None
    lat_p90_ms:                    float | None = None
    lat_p99_ms:                    float | None = None
    lat_mean_ms:                   float | None = None
    lat_std_ms:                    float | None = None
    requests_per_second:           float | None = None
    throughput_tokens_per_second:  float | None = None
    total_output_tokens:           int   | None = None
    success_rate:                  float | None = None
    total_requests:                int   | None = None
    failed_requests:               int   | None = None


@dataclass
class ConcurrencyRecord:
    concurrency_level: int
    requests_per_second: float | None = None
    latency_p95_ms:      float | None = None
    latency_mean_ms:     float | None = None
    success_rate:        float | None = None
    total_tokens:        int   | None = None
    duration_s:          float | None = None


@dataclass
class RunRecord:
    model_id:            str
    model_display_name:  str             = ""
    endpoint_id:         str | None      = None
    platform:            str | None      = None
    preset:              str | None      = None
    timestamp:           datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    deployment:          DeploymentRecord  = field(default_factory=DeploymentRecord)
    performance:         PerformanceRecord = field(default_factory=PerformanceRecord)
    concurrency:         list[ConcurrencyRecord] = field(default_factory=list)
    benchmark_duration_s: float | None    = None
    notes:               str | None      = None
    run_id:              str             = field(default_factory=lambda: str(uuid.uuid4())[:8])


# ── Repository ─────────────────────────────────────────────────────────────────

class BenchmarkRepository:

    def __init__(self, session: Session) -> None:
        self._db = session

    # ── write ──────────────────────────────────────────────────────────────────

    def save_run(self, record: RunRecord) -> str:
        """Persist a complete benchmark run.  Returns run_id."""
        run = BenchmarkRun(
            run_id=record.run_id,
            timestamp=record.timestamp,
            endpoint_id=record.endpoint_id,
            model_id=record.model_id,
            model_display_name=record.model_display_name,
            platform=record.platform,
            preset=record.preset,
        )
        run.deployment = DeploymentMetrics(
            endpoint_creation_time_s=record.deployment.endpoint_creation_time_s,
            time_to_ready_s=record.deployment.time_to_ready_s,
            deletion_time_s=record.deployment.deletion_time_s,
        )
        run.performance = PerformanceMetrics(
            ttft_ms=record.performance.ttft_ms,
            itl_mean_ms=record.performance.itl_mean_ms,
            itl_p50_ms=record.performance.itl_p50_ms,
            itl_p90_ms=record.performance.itl_p90_ms,
            itl_p99_ms=record.performance.itl_p99_ms,
            itl_tokens_per_second=record.performance.itl_tokens_per_second,
            latency_ms=record.performance.latency_ms,
            latency_tokens_per_second=record.performance.latency_tokens_per_second,
            lat_p50_ms=record.performance.lat_p50_ms,
            lat_p90_ms=record.performance.lat_p90_ms,
            lat_p99_ms=record.performance.lat_p99_ms,
            lat_mean_ms=record.performance.lat_mean_ms,
            lat_std_ms=record.performance.lat_std_ms,
            requests_per_second=record.performance.requests_per_second,
            throughput_tokens_per_second=record.performance.throughput_tokens_per_second,
            total_output_tokens=record.performance.total_output_tokens,
            success_rate=record.performance.success_rate,
            total_requests=record.performance.total_requests,
            failed_requests=record.performance.failed_requests,
        )
        run.concurrency = [
            ConcurrencyResult(
                concurrency_level=c.concurrency_level,
                requests_per_second=c.requests_per_second,
                latency_p95_ms=c.latency_p95_ms,
                latency_mean_ms=c.latency_mean_ms,
                success_rate=c.success_rate,
                total_tokens=c.total_tokens,
                duration_s=c.duration_s,
            )
            for c in record.concurrency
        ]
        run.meta = RunMeta(
            benchmark_duration_s=record.benchmark_duration_s,
            total_benchmark_requests=record.performance.total_requests,
            notes=record.notes,
        )
        self._db.add(run)
        self._db.commit()
        return record.run_id

    def update_deletion_time(self, run_id: str, deletion_time_s: float) -> None:
        """Patch deletion_time after endpoint is deleted."""
        row = self._db.query(DeploymentMetrics).filter_by(run_id=run_id).first()
        if row:
            row.deletion_time_s = deletion_time_s
            self._db.commit()

    def add_concurrency_results(self, run_id: str, results: list[ConcurrencyRecord]) -> None:
        """Append concurrency sweep results to an existing run."""
        for c in results:
            self._db.add(ConcurrencyResult(
                run_id=run_id,
                concurrency_level=c.concurrency_level,
                requests_per_second=c.requests_per_second,
                latency_p95_ms=c.latency_p95_ms,
                latency_mean_ms=c.latency_mean_ms,
                success_rate=c.success_rate,
                total_tokens=c.total_tokens,
                duration_s=c.duration_s,
            ))
        self._db.commit()

    def delete_run(self, run_id: str) -> None:
        row = self._db.query(BenchmarkRun).filter_by(run_id=run_id).first()
        if row:
            self._db.delete(row)
            self._db.commit()

    # ── read ───────────────────────────────────────────────────────────────────

    def list_runs(
        self,
        model_filter: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return run summaries as plain dicts (safe for Streamlit)."""
        q = self._db.query(BenchmarkRun)
        if model_filter:
            q = q.filter(BenchmarkRun.model_id == model_filter)
        if start_date:
            q = q.filter(BenchmarkRun.timestamp >= start_date)
        if end_date:
            q = q.filter(BenchmarkRun.timestamp <= end_date)
        runs = q.order_by(BenchmarkRun.timestamp.desc()).limit(limit).all()
        return [self._run_to_dict(r) for r in runs]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._db.query(BenchmarkRun).filter_by(run_id=run_id).first()
        return self._run_to_dict(row) if row else None

    def get_concurrency_results(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self._db.query(ConcurrencyResult)
            .filter_by(run_id=run_id)
            .order_by(ConcurrencyResult.concurrency_level)
            .all()
        )
        return [
            {
                "concurrency": r.concurrency_level,
                "rps": r.requests_per_second,
                "p95_ms": r.latency_p95_ms,
                "mean_ms": r.latency_mean_ms,
                "success_rate": r.success_rate,
                "tokens": r.total_tokens,
                "duration_s": r.duration_s,
            }
            for r in rows
        ]

    def get_platform_summary(self) -> dict[str, Any]:
        """Aggregate stats for the Home dashboard."""
        runs = self._db.query(BenchmarkRun).all()
        if not runs:
            return {"total_runs": 0, "models_tested": 0, "avg_ttft_ms": None, "avg_rps": None}

        perfs = [r.performance for r in runs if r.performance]
        ttfts = [p.ttft_ms for p in perfs if p.ttft_ms]
        rpss  = [p.requests_per_second for p in perfs if p.requests_per_second]
        models = {r.model_id for r in runs}

        return {
            "total_runs":    len(runs),
            "models_tested": len(models),
            "avg_ttft_ms":   sum(ttfts) / len(ttfts) if ttfts else None,
            "avg_rps":       sum(rpss)  / len(rpss)  if rpss  else None,
        }

    def get_distinct_models(self) -> list[str]:
        rows = self._db.query(BenchmarkRun.model_id).distinct().all()
        return [r[0] for r in rows]

    def get_trend_data(self, limit: int = 30) -> list[dict[str, Any]]:
        """TTFT + throughput over time for trend charts."""
        runs = (
            self._db.query(BenchmarkRun)
            .order_by(BenchmarkRun.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows = []
        for r in reversed(runs):
            p = r.performance
            rows.append({
                "run_id":    r.run_id,
                "timestamp": r.timestamp,
                "model":     r.model_display_name or r.model_id,
                "ttft_ms":   p.ttft_ms if p else None,
                "rps":       p.requests_per_second if p else None,
                "ttr_s":     r.deployment.time_to_ready_s if r.deployment else None,
            })
        return rows

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _run_to_dict(r: BenchmarkRun) -> dict[str, Any]:
        p = r.performance
        d = r.deployment
        return {
            "run_id":          r.run_id,
            "timestamp":       r.timestamp,
            "model_id":        r.model_id,
            "model":           r.model_display_name or r.model_id,
            "platform":        r.platform,
            "preset":          r.preset,
            "endpoint_id":     r.endpoint_id,
            # deployment
            "creation_s":      d.endpoint_creation_time_s if d else None,
            "ttr_s":           d.time_to_ready_s          if d else None,
            "deletion_s":      d.deletion_time_s          if d else None,
            # performance
            "ttft_ms":         p.ttft_ms                      if p else None,
            "itl_mean_ms":     p.itl_mean_ms                  if p else None,
            "itl_p90_ms":      p.itl_p90_ms                   if p else None,
            "tok_per_s":       p.itl_tokens_per_second         if p else None,
            "latency_ms":      p.latency_ms                    if p else None,
            "lat_p50_ms":      p.lat_p50_ms                    if p else None,
            "lat_p90_ms":      p.lat_p90_ms                    if p else None,
            "lat_p99_ms":      p.lat_p99_ms                    if p else None,
            "rps":             p.requests_per_second            if p else None,
            "tput_tok_s":      p.throughput_tokens_per_second   if p else None,
            "success_rate":    p.success_rate                   if p else None,
            "has_concurrency": len(r.concurrency) > 0,
        }
