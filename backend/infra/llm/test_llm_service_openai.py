from __future__ import annotations

import os

import pytest

pytest.importorskip("openai")

from backend.infra.llm.llm_service_openai import OpenAICompatibleLLMService


@pytest.mark.skipif(
    not all([os.getenv("LLM_MODEL_ID"), os.getenv("LLM_API_KEY")]),
    reason="真实 LLM 集成测试需要 LLM_MODEL_ID 和 LLM_API_KEY",
)
def test_complete_with_real_openai_compatible_service():
    service = OpenAICompatibleLLMService(
        model=os.environ["LLM_MODEL_ID"],
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.getenv("LLM_BASE_URL") or None,
    )

    result = service.complete(messages=[{"role": "user", "content": "hello"}])

    assert result
