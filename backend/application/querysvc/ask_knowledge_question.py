from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List

from backend.domain.domainsvc.llm_service import LLMService
from backend.domain.knowledge.entities import DocumentChunk
from backend.domain.retrieval.services import TextEmbeddingService, VectorStore
from backend.infra.persistence.document_repository import DocumentRepository
from backend.shared.config import Settings
from backend.shared.errors import AppError


class AskKnowledgeQuestionUseCase:
    def __init__(
        self,
        settings: Settings,
        repository: DocumentRepository,
        embedding_service: TextEmbeddingService,
        vector_store: VectorStore,
        llm_service: LLMService,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._llm_service = llm_service

    def execute(self, question: str) -> dict:
        question = (question or "").strip()
        if self._repository.ready_count() == 0:
            return _empty_knowledge_base()

        if _needs_clarification(question):
            return _clarification()

        try:
            query_embedding = self._embedding_service.embed_query(question)
            evidence = self._vector_store.query_chunks(
                collection_name=self._settings.chroma_collection,
                query_embedding=query_embedding,
                top_k=self._settings.retrieval_top_k,
                min_score=self._settings.retrieval_min_score,
            )
        except Exception as exc:
            raise AppError(
                "QA_RETRIEVAL_FAILED",
                "检索服务暂时不可用，未生成未经验证的回答",
                500,
            ) from exc

        if not evidence:
            return _refusal()

        if not _evidence_supports_question(question, evidence):
            return _refusal()

        try:
            raw_result = self._llm_service.complete(_build_messages(question, evidence))
            payload = _parse_llm_json(str(raw_result))
        except Exception as exc:
            raise AppError("QA_GENERATION_FAILED", "本次问答未完成", 500) from exc

        return _normalize_llm_result(question, payload, evidence)


def _build_messages(question: str, evidence: List[DocumentChunk]) -> List[Dict[str, str]]:
    evidence_payload = [
        {
            "chunkId": chunk.id,
            "documentId": chunk.document_id,
            "documentName": chunk.document_name,
            "headingPath": chunk.heading_path,
            "score": round(chunk.score, 4),
            "text": chunk.text,
        }
        for chunk in evidence
    ]
    return [
        {
            "role": "system",
            "content": (
                "你是 wishub 严格知识库问答助手。只能使用用户消息中的 evidence 回答。"
                "不得使用常识、训练知识、联网内容或猜测。"
                "如果证据不足，返回 refusal；如果问题缺少对象或条件，返回 clarification。"
                "必须只输出 JSON，不要输出 Markdown。"
                "answer 类型必须包含 answer 和 citations，citations 只能引用 evidence 中的 chunkId。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "evidence": evidence_payload,
                    "responseSchema": {
                        "type": "answer | refusal | clarification",
                        "answer": "仅 answer 类型需要",
                        "message": "refusal/clarification 类型需要",
                        "detail": "refusal/clarification 类型需要",
                        "citations": [{"chunkId": "必须来自 evidence"}],
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _normalize_llm_result(question: str, payload: dict, evidence: List[DocumentChunk]) -> dict:
    result_type = payload.get("type")
    if result_type == "clarification":
        return {
            "type": "clarification",
            "message": payload.get("message") or "请补充问题信息",
            "detail": payload.get("detail")
            or "当前问题缺少具体对象或使用场景。请补充产品、功能或条件后再提问。",
        }

    if result_type == "refusal":
        return {
            "type": "refusal",
            "message": payload.get("message") or "当前知识库暂无相关依据",
            "detail": payload.get("detail")
            or "这个问题无法从当前知识库中的 Markdown 文档确认。你可以换一种问法，或补充更具体的关键词。",
            "citations": [],
        }

    if result_type != "answer":
        return _refusal()

    chunks_by_id = {chunk.id: chunk for chunk in evidence}
    cited_chunks = _extract_cited_chunks(payload.get("citations", []), chunks_by_id)
    answer = str(payload.get("answer") or "").strip()
    if not answer or not cited_chunks:
        return _refusal()

    citations = [_citation(chunk) for chunk in cited_chunks]
    return {
        "type": "answer",
        "question": question,
        "answer": answer,
        "citations": citations,
        "checks": {
            "foundEvidence": True,
            "externalKnowledgeUsed": False,
            "citationDocumentCount": len({item["documentId"] for item in citations}),
        },
    }


def _extract_cited_chunks(
    citations: Iterable[dict],
    chunks_by_id: Dict[str, DocumentChunk],
) -> List[DocumentChunk]:
    cited: list[DocumentChunk] = []
    seen: set[str] = set()
    for citation in citations:
        chunk_id = str(citation.get("chunkId") or "")
        if chunk_id in chunks_by_id and chunk_id not in seen:
            cited.append(chunks_by_id[chunk_id])
            seen.add(chunk_id)
    return cited


def _citation(chunk: DocumentChunk) -> dict:
    return {
        "documentId": chunk.document_id,
        "documentName": chunk.document_name,
        "chunkId": chunk.id,
        "headingPath": chunk.heading_path,
        "excerpt": _excerpt(_strip_markdown(chunk.text), 180),
    }


def _needs_clarification(question: str) -> bool:
    return not question or (len(question) <= 4 and not re.search(r"[a-z0-9]", question.lower()))


def _evidence_supports_question(question: str, evidence: List[DocumentChunk]) -> bool:
    question_terms = _meaningful_terms(question)
    if not question_terms:
        return False
    evidence_terms: set[str] = set()
    for chunk in evidence:
        evidence_terms.update(_meaningful_terms(chunk.text))
        if chunk.heading_path:
            evidence_terms.update(_meaningful_terms(chunk.heading_path))
        evidence_terms.update(_meaningful_terms(chunk.document_name))
    return bool(question_terms & evidence_terms)


def _meaningful_terms(text: str) -> set[str]:
    lowered = text.lower()
    terms: set[str] = set(re.findall(r"[a-z0-9_]{2,}", lowered))
    for span in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        if len(span) <= 8:
            terms.add(span)
        for width in (2, 3):
            for index in range(max(0, len(span) - width + 1)):
                terms.add(span[index : index + width])
    return {term for term in terms if term not in _STOP_TERMS}


def _empty_knowledge_base() -> dict:
    return {
        "type": "empty_knowledge_base",
        "message": "当前没有可用于问答的文档",
        "detail": "先上传并处理完成一个 Markdown 文档，再开始提问。",
    }


def _clarification() -> dict:
    return {
        "type": "clarification",
        "message": "请补充问题信息",
        "detail": "当前问题缺少具体对象或使用场景。请补充产品、功能或条件后再提问。",
    }


def _refusal() -> dict:
    return {
        "type": "refusal",
        "message": "当前知识库暂无相关依据",
        "detail": "这个问题无法从当前知识库中的 Markdown 文档确认。你可以换一种问法，或补充更具体的关键词。",
        "citations": [],
    }


def _excerpt(text: str, max_length: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _strip_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


_STOP_TERMS = {
    "一个",
    "一下",
    "以及",
    "什么",
    "哪些",
    "如何",
    "怎么",
    "是否",
    "可以",
    "当前",
    "这个",
    "那个",
    "知识库",
    "知识",
    "文档",
    "问题",
    "系统",
    "使用",
    "需要",
    "进行",
    "支持",
    "说明",
    "the",
    "and",
    "for",
    "with",
}
