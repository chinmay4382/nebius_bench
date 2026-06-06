import logging
import time
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)

_TTFT_PROMPT = "Explain quantum computing in exactly three sentences."


@dataclass
class TTFTResult:
    ttft_ms: float
    success: bool
    error: str | None = None


def measure_ttft(
    client: OpenAI,
    model: str,
    prompt: str = _TTFT_PROMPT,
    max_tokens: int = 512,
) -> TTFTResult:
    """Measure Time To First Token using a streaming request."""
    request_start = time.perf_counter()
    first_token_time: float | None = None

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if first_token_time is None:
                choices = chunk.choices
                if choices and choices[0].delta.content:
                    first_token_time = time.perf_counter()
                    break

        stream.close()

        if first_token_time is None:
            return TTFTResult(ttft_ms=0.0, success=False, error="No tokens received in stream")

        ttft_ms = (first_token_time - request_start) * 1000
        logger.debug("TTFT: %.1fms", ttft_ms)
        return TTFTResult(ttft_ms=ttft_ms, success=True)

    except Exception as exc:
        logger.error("TTFT measurement failed: %s", exc)
        return TTFTResult(ttft_ms=0.0, success=False, error=str(exc))
