from __future__ import annotations

import json
from typing import Dict, Generator, List, Union

from backend.domain.domainsvc.llm_service import LLMService


class EvidenceBoundLLMService(LLMService):
    """Offline LLM-compatible service that only formats provided evidence."""

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream: bool = False,
        max_tokens: int = 2048,
    ) -> Union[str, Generator[str, None, None]]:
        del temperature, stream, max_tokens
        payload = json.loads(messages[-1]["content"])
        question = str(payload.get("question", "")).strip()
        evidence = payload.get("evidence", [])

        if len(question) <= 4:
            return json.dumps(
                {
                    "type": "clarification",
                    "message": "请补充问题信息",
                    "detail": "当前问题缺少具体对象或使用场景。请补充产品、功能或条件后再提问。",
                },
                ensure_ascii=False,
            )

        if not evidence:
            return json.dumps(
                {
                    "type": "refusal",
                    "message": "当前知识库暂无相关依据",
                    "detail": "这个问题无法从当前知识库中的 Markdown 文档确认。你可以换一种问法，或补充更具体的关键词。",
                    "citations": [],
                },
                ensure_ascii=False,
            )

        primary = evidence[0]
        sentences = []
        for item in evidence[:2]:
            text = " ".join(str(item.get("text", "")).split())
            if text:
                sentences.append(text[:180])

        return json.dumps(
            {
                "type": "answer",
                "answer": f"根据《{primary.get('documentName')}》，" + "；".join(sentences),
                "citations": [{"chunkId": item.get("chunkId")} for item in evidence[:2]],
            },
            ensure_ascii=False,
        )
