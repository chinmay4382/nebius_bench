import logging
import os
import random
import string
import time
from dataclasses import dataclass
from datetime import datetime

from .nebius_client import run_nebius_command

logger = logging.getLogger(__name__)

# Real presets from `nebius compute platform list` — only 1-GPU and 8-GPU exist.
PRESET_MAP: dict[int, dict[str, str]] = {
    1: {
        "gpu-h200-sxm": "1gpu-16vcpu-200gb",
        "gpu-b200-sxm": "1gpu-20vcpu-224gb",
        "gpu-rtx6000":  "1gpu-24vcpu-218gb",
    },
    8: {
        "gpu-h200-sxm": "8gpu-128vcpu-1600gb",
        "gpu-b200-sxm": "8gpu-160vcpu-1792gb",
        "gpu-rtx6000":  "8gpu-192vcpu-1744gb",
    },
}

ENGINE_IMAGES: dict[str, str] = {
    "vllm":   "vllm/vllm-openai:latest",
    "sglang": "lmsysorg/sglang:latest",
}


def _build_engine_args(
    engine: str,
    model_id: str,
    served_model_name: str,
    max_model_len: int,
    gpu_count: int,
    # shared
    quantization: str | None = None,
    dtype: str = "auto",
    # vLLM-specific
    gpu_memory_utilization: float = 0.90,
    enable_prefix_caching: bool = False,
    max_num_seqs: int | None = None,
    # SGLang-specific
    mem_fraction_static: float = 0.88,
    disable_radix_cache: bool = False,
    max_running_requests: int | None = None,
    attention_backend: str = "flashinfer",
) -> str:
    if engine == "sglang":
        tp = f" --tp {gpu_count}" if gpu_count > 1 else ""
        args = (
            f"--model-path {model_id} "
            f"--served-model-name {served_model_name} "
            f"--max-total-tokens {max_model_len} "
            f"--host 0.0.0.0 "
            f"--port 8000"
            f"{tp}"
            f" --dtype {dtype}"
            f" --mem-fraction-static {mem_fraction_static}"
            f" --attention-backend {attention_backend}"
        )
        if quantization and quantization != "none":
            args += f" --quantization {quantization}"
        if disable_radix_cache:
            args += " --disable-radix-cache"
        if max_running_requests is not None:
            args += f" --max-running-requests {max_running_requests}"
        return args

    # vllm
    tp = f" --tensor-parallel-size {gpu_count}" if gpu_count > 1 else ""
    args = (
        f"--model {model_id} "
        f"--served-model-name {served_model_name} "
        f"--max-model-len {max_model_len} "
        f"--host 0.0.0.0 "
        f"--port 8000"
        f"{tp}"
        f" --dtype {dtype}"
        f" --gpu-memory-utilization {gpu_memory_utilization}"
    )
    if quantization and quantization != "none":
        args += f" --quantization {quantization}"
    if enable_prefix_caching:
        args += " --enable-prefix-caching"
    if max_num_seqs is not None:
        args += f" --max-num-seqs {max_num_seqs}"
    return args


def resolve_preset(gpu_count: int, platform: str) -> str:
    """Return the correct preset name for the given gpu_count + platform combination."""
    bucket = PRESET_MAP.get(gpu_count)
    if bucket is None:
        raise ValueError(
            f"No preset defined for gpu_count={gpu_count}. "
            f"Valid counts: {list(PRESET_MAP)}"
        )
    preset = bucket.get(platform)
    if preset is None:
        raise ValueError(
            f"No preset defined for platform={platform!r} with gpu_count={gpu_count}. "
            f"Known platforms: {list(bucket)}"
        )
    return preset


@dataclass
class EndpointCreationResult:
    endpoint_id: str
    request_timestamp: float
    creation_duration_seconds: float
    preset_used: str


def create_endpoint(
    model_id: str,
    image: str,
    platform: str,
    gpu_count: int,
    served_model_name: str,
    max_model_len: int = 4096,
    disk_size: str = "250Gi",
    name: str | None = None,
    hf_token: str | None = None,
    engine: str = "vllm",
    image_tag: str = "latest",
    quantization: str | None = None,
    dtype: str = "auto",
    gpu_memory_utilization: float = 0.90,
    enable_prefix_caching: bool = False,
    max_num_seqs: int | None = None,
    mem_fraction_static: float = 0.88,
    disable_radix_cache: bool = False,
    max_running_requests: int | None = None,
    attention_backend: str = "flashinfer",
) -> EndpointCreationResult:
    """Create a Nebius AI endpoint using vLLM or SGLang for the given model."""
    preset = resolve_preset(gpu_count, platform)

    if name is None:
        model_slug = served_model_name.lower().replace("_", "-")[:20]
        dt_str     = datetime.now().strftime("%Y%m%d%H%M%S")
        rand_str   = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        name = f"geM-{engine}-{model_slug}-{dt_str}-{rand_str}"

    request_timestamp = time.time()

    base_image = ENGINE_IMAGES.get(engine, image)
    # Allow pinning a specific image tag (e.g. v0.8.5 instead of latest)
    if ":" in base_image:
        base_image = base_image.rsplit(":", 1)[0]
    effective_image = f"{base_image}:{image_tag}"

    engine_args = _build_engine_args(
        engine, model_id, served_model_name, max_model_len, gpu_count,
        quantization=quantization,
        dtype=dtype,
        gpu_memory_utilization=gpu_memory_utilization,
        enable_prefix_caching=enable_prefix_caching,
        max_num_seqs=max_num_seqs,
        mem_fraction_static=mem_fraction_static,
        disable_radix_cache=disable_radix_cache,
        max_running_requests=max_running_requests,
        attention_backend=attention_backend,
    )

    cmd_args: list[str] = [
        "ai", "endpoint", "create",
        "--name", name,
        "--image", effective_image,
        "--platform", platform,
        "--preset", preset,
        "--args", engine_args,
        "--container-port", "8000",
        "--disk-size", disk_size,
        "--public",
        "--auth", "token",
    ]

    resolved_hf_token = hf_token or os.getenv("HUGGING_FACE_HUB_TOKEN")
    if resolved_hf_token:
        cmd_args.extend(["--env", f"HUGGING_FACE_HUB_TOKEN={resolved_hf_token}"])

    parent_id = os.getenv("NEBIUS_PROJECT_ID")
    if parent_id:
        cmd_args.extend(["--parent-id", parent_id])

    logger.info(
        "Creating endpoint: name=%s model=%s engine=%s platform=%s preset=%s",
        name, model_id, engine, platform, preset,
    )

    response = run_nebius_command(cmd_args, timeout=120)

    endpoint_id = (
        response.get("metadata", {}).get("id")
        or response.get("id")
        or response.get("resource_id")
    )

    if not endpoint_id:
        raise ValueError(f"Could not extract endpoint ID from response: {response}")

    duration = time.time() - request_timestamp
    logger.info("Endpoint created: id=%s preset=%s duration=%.1fs", endpoint_id, preset, duration)

    return EndpointCreationResult(
        endpoint_id=endpoint_id,
        request_timestamp=request_timestamp,
        creation_duration_seconds=duration,
        preset_used=preset,
    )
