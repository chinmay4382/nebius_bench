"""SQLAlchemy ORM models for Nebius Endpoint Lab."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    run_id:              Mapped[str]            = mapped_column(String, primary_key=True)
    timestamp:           Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    endpoint_id:         Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    model_id:            Mapped[str]            = mapped_column(String, nullable=False)
    model_display_name:  Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    platform:            Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    preset:              Mapped[Optional[str]]  = mapped_column(String, nullable=True)

    deployment:   Mapped[Optional[DeploymentMetrics]]    = relationship(back_populates="run", uselist=False,  cascade="all, delete-orphan")
    performance:  Mapped[Optional[PerformanceMetrics]]   = relationship(back_populates="run", uselist=False,  cascade="all, delete-orphan")
    concurrency:  Mapped[list[ConcurrencyResult]]        = relationship(back_populates="run", cascade="all, delete-orphan")
    meta:         Mapped[Optional[RunMeta]]              = relationship(back_populates="run", uselist=False,  cascade="all, delete-orphan")


class DeploymentMetrics(Base):
    __tablename__ = "deployment_metrics"

    id:                       Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id:                   Mapped[str]            = mapped_column(ForeignKey("benchmark_runs.run_id"), nullable=False)
    endpoint_creation_time_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_ready_s:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deletion_time_s:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    run: Mapped[BenchmarkRun] = relationship(back_populates="deployment")


class PerformanceMetrics(Base):
    __tablename__ = "performance_metrics"

    id:     Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("benchmark_runs.run_id"), nullable=False)

    # TTFT
    ttft_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ITL
    itl_mean_ms:         Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    itl_p50_ms:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    itl_p90_ms:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    itl_p99_ms:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    itl_tokens_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # End-to-end latency
    latency_ms:                Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_tokens_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Latency distribution (20-sample)
    lat_p50_ms:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lat_p90_ms:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lat_p99_ms:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lat_mean_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lat_std_ms:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Throughput
    requests_per_second:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    throughput_tokens_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_output_tokens:          Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    success_rate:                 Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_requests:               Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    failed_requests:              Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)

    run: Mapped[BenchmarkRun] = relationship(back_populates="performance")


class ConcurrencyResult(Base):
    __tablename__ = "concurrency_results"

    id:                Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id:            Mapped[str]            = mapped_column(ForeignKey("benchmark_runs.run_id"), nullable=False)
    concurrency_level: Mapped[int]            = mapped_column(Integer, nullable=False)
    requests_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_p95_ms:    Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_mean_ms:   Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    success_rate:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_tokens:      Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    duration_s:        Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    run: Mapped[BenchmarkRun] = relationship(back_populates="concurrency")


class RunMeta(Base):
    __tablename__ = "run_meta"

    id:                       Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id:                   Mapped[str]            = mapped_column(ForeignKey("benchmark_runs.run_id"), nullable=False)
    benchmark_duration_s:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_benchmark_requests: Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    notes:                    Mapped[Optional[str]]   = mapped_column(Text, nullable=True)

    run: Mapped[BenchmarkRun] = relationship(back_populates="meta")
