from __future__ import annotations

from typing import Dict, Generator, List, Optional, Union

from backend.domain.domainsvc.llm_service import LLMService


class OpenAICompatibleLLMService(LLMService):
    """OpenAI-compatible chat completion service."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        if not model or not api_key:
            raise ValueError("LLM_MODEL_ID 和 LLM_API_KEY 必须配置")

        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("缺少 openai 依赖，无法启用真实 LLM 服务") from exc

        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout)

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream: bool = False,
        max_tokens: int = 2048,
    ) -> Union[str, Generator[str, None, None]]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        if not stream:
            return (response.choices[0].message.content or "").strip()

        def stream_generator() -> Generator[str, None, None]:
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        return stream_generator()


GeneralLLMService = OpenAICompatibleLLMService
