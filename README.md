# Nebius Endpoint Lab

End-to-end benchmark for [Nebius AI](https://nebius.com) Serverless Endpoint lifecycle and serving performance.

```
┌─────────────────────────────────────────────────────┐
│          Nebius Endpoint Lab — Streamlit UI          │
├─────────────────────────────────────────────────────┤
│  1. Select model → Create Endpoint                  │
│  2. Watch deployment progress (live status card)    │
│  3. Click Run Benchmark when RUNNING                │
│  4. View TTFT / Latency / Throughput metrics        │
│  5. Download JSON or Markdown report                │
│  6. Delete endpoint                                 │
└─────────────────────────────────────────────────────┘
```

## Architecture

```
app/Home.py  (Streamlit single-page)
    │
    ├─ orchestrator/         # Nebius lifecycle (CLI wrapper)
    │   ├─ nebius_client.py  # subprocess → nebius CLI
    │   ├─ create_endpoint.py
    │   ├─ get_status.py
    │   ├─ wait_until_ready.py
    │   └─ delete_endpoint.py
    │
    ├─ benchmark/            # OpenAI-compatible serving benchmarks
    │   ├─ ttft.py           # Time To First Token (streaming)
    │   ├─ latency.py        # End-to-end latency (non-streaming)
    │   ├─ throughput.py     # 10 concurrent requests
    │   └─ benchmark_runner.py
    │
    ├─ reports/
    │   ├─ json_report.py
    │   └─ markdown_report.py
    │
    └─ config/models.yaml    # Model catalogue
```

See [docs/architecture.md](docs/architecture.md) for the full design.

---

## Prerequisites

### 1. Nebius CLI

```bash
curl -sSL https://storage.eu-north1.nebius.cloud/nebius-cli/install.sh | bash
```

Verify:

```bash
nebius --version
```

### 2. Authenticate

```bash
nebius iam login
```

Or with a service account:

```bash
nebius profile create --service-account-key /path/to/key.json
```

Confirm you can list AI endpoints:

```bash
nebius ai endpoint list
```

### 3. Python 3.12+

```bash
python --version   # 3.12+
```

---

## Running Locally

```bash
git clone <repo>
cd nebius-endpoint-lab

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set HUGGING_FACE_HUB_TOKEN for gated models

# Launch
streamlit run app/Home.py
```

Open `http://localhost:8501` in your browser.

---

## Running with Docker

```bash
docker build -t nebius-endpoint-lab .

docker run -p 8501:8501 \
  -v ~/.nebius:/root/.nebius:ro \
  -e HUGGING_FACE_HUB_TOKEN=hf_xxx \
  nebius-endpoint-lab
```

The Nebius CLI config directory is mounted read-only so the container inherits your local authentication.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HUGGING_FACE_HUB_TOKEN` | For gated models | HF token for LLaMA 4, etc. |
| `NEBIUS_PROJECT_ID` | No | Overrides CLI default project |
| `NEBIUS_PROFILE` | No | Named Nebius CLI profile |
| `NEBIUS_API_KEY` | No | API key for pre-existing endpoints |

---

## Model Configuration

Edit `config/models.yaml` to add or modify models:

```yaml
models:
  - id: my-model
    display_name: "My Model"
    image: "vllm/vllm-openai:latest"
    model_id: "org/model-name-on-hf"
    served_model_name: "my-model"
    platform: "gpu-h200-sxm"
    preset: "1gpu-16vcpu-200gb"
    max_model_len: 4096
    max_tokens: 512
    disk_size: "250Gi"
```

Available platforms and presets:

```bash
nebius compute platform list
```

---

## Sample Benchmark Output

### JSON

```json
{
  "model": "qwen3",
  "timestamp": "2026-01-01T12:00:00Z",
  "endpoint_creation_time_seconds": 8.2,
  "time_to_ready_seconds": 312.0,
  "ttft_ms": 420.0,
  "latency_ms": 1750.0,
  "requests_per_second": 3.8,
  "success_rate": 1.0,
  "total_requests": 10,
  "successful_requests": 10,
  "failed_requests": 0,
  "deletion_time_seconds": 12.1
}
```

### Markdown

```markdown
# Nebius AI Endpoint Benchmark Report

## Results

| Metric | Value |
|--------|-------|
| Model | qwen3 |
| Time To Ready | 312.0s |
| TTFT | 420ms |
| Latency (E2E) | 1750ms |
| Throughput | 3.80 rps |
| Success Rate | 100.0% |
```

---

## Notes

- Endpoint creation triggers VM provisioning which can take **5–10 minutes** for large models.
- vLLM downloads the model from HuggingFace on first boot; this adds to time-to-ready.
- Keep `max_model_len` conservative (4096–8192) to avoid OOM on smaller GPU presets.
- The benchmark sends **12 total requests** (1 TTFT + 1 latency + 10 throughput); costs are minimal.
