"""
HuggingFace target adapter - implements TargetModelPort.

Calls the HuggingFace router OpenAI-compatible chat completions endpoint with
tenacity exponential backoff on transient statuses (429/5xx/timeout). Ported
from the PoC HuggingFaceClient, narrowed to the multi-turn chat the engine
needs.
"""
from __future__ import annotations

import time

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from crescendo.domain.models import ChatResult

_RETRYABLE_STATUSES = {429, 502, 503, 504}


class _RetryableHTTPError(Exception):
    """Marker so tenacity only retries the transient-status branch."""


class HuggingFaceTarget:
    """Implements TargetModelPort against router.huggingface.co/v1."""

    def __init__(
        self,
        *,
        api_key: str,
        model_map: dict[str, str],
        api_url: str = "https://router.huggingface.co/v1",
        timeout: int = 45,
        max_retries: int = 3,
        max_tokens: int = 1024,
        top_p: float = 0.9,
    ) -> None:
        self._api_key = api_key
        self._model_map = model_map
        self._api_url = api_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        self._top_p = top_p

    def _model_id(self, model: str) -> str:
        return self._model_map.get(model, model)

    async def _post(
        self, model: str, messages: list[dict[str, str]], temperature: float
    ) -> ChatResult:
        start = time.time()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model_id(model),
                        "messages": messages,
                        "max_tokens": self._max_tokens,
                        "temperature": temperature,
                        "top_p": self._top_p,
                    },
                )
            except httpx.TimeoutException as e:
                raise _RetryableHTTPError("timeout") from e

        latency = (time.time() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            text = (
                data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            return ChatResult(text=text.strip(), latency_ms=latency, success=True)

        if resp.status_code in _RETRYABLE_STATUSES:
            raise _RetryableHTTPError(f"transient {resp.status_code}: {resp.text[:200]}")

        err = resp.text
        try:
            err = resp.json().get("error", {}).get("message", err)
        except Exception:  # noqa: BLE001
            pass
        return ChatResult(
            text=None,
            latency_ms=latency,
            success=False,
            error=f"API error: {resp.status_code} - {err}",
        )

    async def chat(
        self, model: str, messages: list[dict[str, str]], temperature: float
    ) -> ChatResult:
        start = time.time()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=15),
                retry=retry_if_exception_type(_RetryableHTTPError),
                reraise=True,
            ):
                with attempt:
                    return await self._post(model, messages, temperature)
        except (_RetryableHTTPError, RetryError) as e:
            return ChatResult(
                text=None,
                latency_ms=(time.time() - start) * 1000,
                success=False,
                error=f"Retries exhausted: {e}",
            )
        except Exception as e:  # noqa: BLE001
            return ChatResult(
                text=None,
                latency_ms=(time.time() - start) * 1000,
                success=False,
                error=str(e),
            )
        # Unreachable, but satisfies type checkers.
        return ChatResult(text=None, latency_ms=0.0, success=False, error="unknown")
