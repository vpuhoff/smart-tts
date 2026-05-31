from __future__ import annotations

import httpx

from elevenlabs_smart_tts.client.retry import async_request_with_retry, request_with_retry
from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.exceptions import OpenRouterAPIError


class OpenRouterClient:
    def __init__(self, config: SmartTTSConfig, *, client: httpx.Client | None = None) -> None:
        self._config = config
        self._client = client or httpx.Client(
            base_url=config.openrouter_base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenRouterClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def enhance_text(
        self,
        text: str,
        system_prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        payload = {
            "model": model or self._config.openrouter_tts_prompt_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": temperature,
        }
        response = request_with_retry(
            lambda: self._client.post("/chat/completions", json=payload),
            max_retries=2,
        )
        if response.status_code >= 400:
            raise OpenRouterAPIError(response.status_code, response.text)
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterAPIError(response.status_code, "Invalid chat completion response") from exc
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterAPIError(response.status_code, "Empty enhancement response")
        return content.strip()


class AsyncOpenRouterClient:
    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.openrouter_base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncOpenRouterClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def enhance_text(
        self,
        text: str,
        system_prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        payload = {
            "model": model or self._config.openrouter_tts_prompt_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": temperature,
        }
        response = await async_request_with_retry(
            lambda: self._client.post("/chat/completions", json=payload),
            max_retries=2,
        )
        if response.status_code >= 400:
            raise OpenRouterAPIError(response.status_code, response.text)
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterAPIError(response.status_code, "Invalid chat completion response") from exc
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterAPIError(response.status_code, "Empty enhancement response")
        return content.strip()
