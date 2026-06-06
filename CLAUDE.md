# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Nebius Endpoint Lab** — a Streamlit app that benchmarks the full lifecycle of [Nebius AI](https://nebius.com) Serverless Endpoints: create → wait for ready → run benchmarks → report → delete.

## Development Commands

```bash
# Install dependencies (Python 3.12+ required)
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Launch the app
streamlit run app/Home.py
```

Open `http://localhost:8501` in your browser.

**Docker:**
```bash
docker build -t nebius-endpoint-lab .
docker run -p 8501:8501 \
  -v ~/.nebius:/root/.nebius:ro \
  -e HUGGING_FACE_HUB_TOKEN=hf_xxx \
  nebius-endpoint-lab
```

## Architecture

The app is a multi-page Streamlit application. All pages live under `app/pages/` and use `sys.path.insert` to import from the root project packages.

**Data flow:**
```
app/Home.py + app/pages/
    │
    ├─ orchestrator/          # Nebius lifecycle via CLI subprocess
    │   └─ nebius_client.py   # All CLI calls go through run_nebius_command()
    │                         # Always uses --format json --no-progress
    │
    ├─ benchmark/             # OpenAI-compatible serving benchmarks
    │   ├─ ttft.py            # Streaming: measures time to first non-empty delta
    │   ├─ latency.py         # Non-streaming: end-to-end round-trip (20 samples)
    │   ├─ throughput.py      # 10 reqs, 5 concurrent workers
    │   ├─ itl.py             # Inter-token latency from streaming chunks
    │   └─ benchmark_runner.py # Orchestrates all benchmark types
    │
    ├─ database/              # SQLite via SQLAlchemy ORM
    │   ├─ models.py          # BenchmarkRun → DeploymentMetrics, PerformanceMetrics,
    │   │                     #   ConcurrencyResult, RunMeta (all cascade-delete)
    │   ├─ migrations.py      # get_session_factory() — auto-creates tables on init
    │   └─ repository.py      # BenchmarkRepository — all DB queries
    │
    ├─ reports/               # Export formats
    │   ├─ json_report.py
    │   ├─ markdown_report.py
    │   └─ html_report.py
    │
    └─ config/models.yaml     # Model catalogue — add/edit models here
```

## Key Design Decisions

- **Nebius CLI via subprocess**: All Nebius API calls invoke the `nebius` CLI binary (found via `~/.nebius/bin` or PATH). No direct API client — this keeps auth handling delegated to the CLI.
- **Streamlit polling**: Status polling uses `time.sleep(5)` + `st.rerun()` in the main thread — no async infrastructure needed.
- **Benchmark in background thread**: The benchmark suite runs in `threading.Thread`; results are written back to `st.session_state` (safe under CPython's GIL for simple reference assignments).
- **Token auth**: Endpoints are created with `--auth token`. The token is read from `spec.auth_token` in the endpoint status JSON and used as the OpenAI `api_key`.
- **Endpoint URL**: Derived from `status.public_endpoints[0]`; `/v1` is appended to form the OpenAI-compatible base URL.
- **SQLite DB**: Stored at `database/nebius_bench.db` (auto-created on first run, not committed).

## Environment Variables

| Variable | Description |
|---|---|
| `HUGGING_FACE_HUB_TOKEN` | Required for gated models (LLaMA 4, etc.) |
| `NEBIUS_PROJECT_ID` | Overrides CLI default project |
| `NEBIUS_PROFILE` | Named Nebius CLI profile |
| `NEBIUS_API_KEY` | API key for pre-existing endpoints not created by the app |

## Adding Models

Edit `config/models.yaml`. Each entry needs: `id`, `display_name`, `image`, `model_id` (HuggingFace path), `served_model_name`, `platform`, `preset`, `max_model_len`, `max_tokens`, `disk_size`.

Run `nebius compute platform list` to see available platforms and presets.

## Nebius CLI Prerequisite

```bash
curl -sSL https://storage.eu-north1.nebius.cloud/nebius-cli/install.sh | bash
nebius iam login
nebius ai endpoint list   # verify auth works
```
