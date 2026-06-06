# Architecture

## Overview

Nebius Endpoint Lab benchmarks the full lifecycle of a Nebius AI Serverless Endpoint — from creation through serving to deletion — in a single Streamlit session.

```
┌──────────────────────────────────────────────────────────────┐
│                      Streamlit UI (app/Home.py)              │
│                                                              │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐  │
│  │  Model   │  │  Status    │  │  Benchmark │  │Reports │  │
│  │ Selector │  │  Card      │  │  Dashboard │  │Download│  │
│  └────┬─────┘  └─────┬──────┘  └─────┬──────┘  └───┬────┘  │
└───────┼──────────────┼────────────────┼─────────────┼───────┘
        │              │                │             │
        ▼              ▼                ▼             ▼
┌───────────────────────────────────────────────────────────────┐
│                     orchestrator/                             │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ create_endpoint │  │  get_status  │  │ delete_endpoint │  │
│  └────────┬────────┘  └──────┬───────┘  └────────┬────────┘  │
│           │                  │                    │           │
│           └──────────────────┴────────────────────┘           │
│                              │                                │
│                    ┌─────────▼─────────┐                      │
│                    │  nebius_client.py │  subprocess → CLI   │
│                    └───────────────────┘                      │
└───────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │   Nebius CLI        │
                   │ nebius ai endpoint  │
                   └──────────┬──────────┘
                              │ HTTPS
                   ┌──────────▼──────────┐
                   │  Nebius Cloud API   │
                   └──────────┬──────────┘
                              │
                   ┌──────────▼──────────┐
                   │  AI Endpoint VM     │
                   │  vllm/vllm-openai   │
                   │  :8000/v1           │
                   └──────────┬──────────┘
                              │ HTTP
        ┌─────────────────────┼─────────────────────────┐
        ▼                     ▼                          ▼
┌──────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│  benchmark/  │   │  benchmark/      │   │  benchmark/         │
│  ttft.py     │   │  latency.py      │   │  throughput.py      │
│  (streaming) │   │  (non-streaming) │   │  (10 concurrent)    │
└──────────────┘   └──────────────────┘   └─────────────────────┘
        │                     │                          │
        └─────────────────────┴──────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  reports/           │
                   │  json_report.py     │
                   │  markdown_report.py │
                   └─────────────────────┘
```

## Workflow State Machine

```
idle ──[Create Endpoint]──► creating
                                │
                           (CLI create call)
                                │
                            polling ──[5s poll loop]──► polling
                                │
                          [state=RUNNING]
                                │
                             ready
                                │
                        [Run Benchmark]
                                │
                          benchmarking ──[background thread]──► benchmarking
                                │
                        [thread complete]
                                │
                            results
                                │
                        [Delete Endpoint]
                                │
                           deleting
                                │
                        (CLI delete call)
                                │
                             results  (deletion_result set)
```

## Key Design Decisions

### Nebius CLI via subprocess
All Nebius API calls go through the official `nebius` CLI binary, invoked with `--format json`. This avoids dealing with raw API authentication and keeps the integration stable across API versions.

### Polling in Streamlit main thread
Status polling uses `time.sleep(5)` + `st.rerun()` in the Streamlit script itself. This is the simplest reliable approach for periodic UI updates without requiring additional async infrastructure.

### Benchmark in background thread
The benchmark suite (TTFT + latency + throughput) runs in a `threading.Thread` so the Streamlit script can show live progress. Results are communicated back via a plain `dict` stored in `st.session_state` (thread-safe for simple reference assignments under CPython's GIL).

### Token auth
Endpoints are created with `--auth token`. The generated token is stored in `spec.auth_token` of the endpoint status JSON and forwarded to the OpenAI client as the `api_key`.

## Endpoint URL Detection

The public endpoint URL is derived from the `status.public_endpoints` array in the Nebius CLI response:

```json
"status": {
  "public_endpoints": ["204.12.168.155:8000"],
  "state": "RUNNING"
}
```

→ `http://204.12.168.155:8000`

The benchmark client appends `/v1` to form the OpenAI-compatible base URL.

## Benchmark Metrics

| Metric | Method | Requests |
|--------|--------|----------|
| TTFT | Streaming — measure gap between send and first non-empty delta | 1 |
| Latency | Non-streaming — measure total round-trip time | 1 |
| Throughput | 10 non-streaming requests, 5 concurrent workers | 10 |
| Success Rate | Fraction of successful throughput requests | 10 |
