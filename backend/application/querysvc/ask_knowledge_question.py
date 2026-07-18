from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import replace
from typing import Dict, Iterable, List, Optional

from backend.domain.domainsvc.llm_service import LLMService
from backend.domain.knowledge.entities import Document, DocumentChunk, DocumentStatus
from backend.domain.retrieval.services import TextEmbeddingService, VectorStore
from backend.infra.persistence.llm_log_repository import LLMCallLogRepository
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
        llm_log_repository: LLMCallLogRepository,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._llm_service = llm_service
        self._llm_log_repository = llm_log_repository

    def execute(self, question: str) -> dict:
        question = (question or "").strip()
        if self._repository.ready_count() == 0:
            return _empty_knowledge_base()

        if _needs_clarification(question):
            return _clarification()

        if _is_catalog_question(question):
            return _answer_catalog_question(question, self._repository.list_documents(status=DocumentStatus.READY.value))

        try:
            ready_chunks = self._repository.list_ready_chunks()
            query_embedding = self._embedding_service.embed_query(question)
            vector_evidence = self._vector_store.query_chunks(
                collection_name=self._settings.chroma_collection,
                query_embedding=query_embedding,
                top_k=_vector_recall_size(self._settings.retrieval_top_k, len(ready_chunks)),
                min_score=self._settings.retrieval_min_score,
            )
            evidence = _hybrid_rerank(
                question,
                vector_evidence,
                ready_chunks,
                self._settings.retrieval_top_k,
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

        messages = _build_messages(question, evidence)
        started_at = time.perf_counter()
        raw_result = None
        payload = None
        final_result = None
        try:
            raw_result = str(self._llm_service.complete(messages))
            payload = _parse_llm_json(str(raw_result))
        except Exception as exc:
            self._record_llm_call(
                question=question,
                status="FAILED",
                request_payload=messages,
                response_text=raw_result,
                parsed_response=payload,
                final_result=None,
                error_message=str(exc),
                started_at=started_at,
            )
            raise AppError("QA_GENERATION_FAILED", "本次问答未完成", 500) from exc

        final_result = _normalize_llm_result(question, payload, evidence)
        self._record_llm_call(
            question=question,
            status="SUCCESS",
            request_payload=messages,
            response_text=raw_result,
            parsed_response=payload,
            final_result=final_result,
            error_message=None,
            started_at=started_at,
        )
        return final_result

    def _record_llm_call(
        self,
        *,
        question: str,
        status: str,
        request_payload: list[dict],
        response_text: Optional[str],
        parsed_response: Optional[dict],
        final_result: Optional[dict],
        error_message: Optional[str],
        started_at: float,
    ) -> None:
        self._llm_log_repository.create(
            question=question,
            model_id=_resolve_llm_model_id(self._settings),
            status=status,
            request_payload=request_payload,
            response_text=response_text,
            parsed_response=parsed_response,
            final_result=final_result,
            error_message=error_message,
            latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
        )


def _resolve_llm_model_id(settings: Settings) -> str:
    provider = settings.llm_provider.lower()
    uses_configured_model = provider == "openai" or (
        provider == "auto" and bool(settings.llm_model_id and settings.llm_api_key)
    )
    if uses_configured_model:
        return settings.llm_model_id
    if provider in {"auto", "offline"}:
        return "offline:evidence-bound"
    return settings.llm_model_id or provider or "unknown"


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


def _is_catalog_question(question: str) -> bool:
    normalized = re.sub(r"\s+", "", question)
    document_intent = any(keyword in normalized for keyword in ("文档", "文件", "资料", "目录"))
    qa_scope_intent = any(keyword in normalized for keyword in ("参与问答", "用于问答", "可问答", "能问答", "可以问答"))
    qa_list_intent = any(keyword in normalized for keyword in ("哪些", "什么", "哪几", "有哪些", "有什么"))
    catalog_list_intent = any(keyword in normalized for keyword in ("有哪些", "有什么", "哪几", "有几", "多少", "列表", "目录"))
    return document_intent and ((qa_scope_intent and qa_list_intent) or catalog_list_intent)


def _answer_catalog_question(question: str, documents: List[Document]) -> dict:
    if not documents:
        return _empty_knowledge_base()

    document_names = [document.filename for document in documents]
    if len(document_names) == 1:
        answer = f"当前可参与问答的文档是《{document_names[0]}》。只有处理成功并处于 READY 状态的 Markdown 文档会进入问答范围。"
    else:
        formatted_names = "、".join(f"《{name}》" for name in document_names)
        answer = f"当前共有 {len(document_names)} 个可参与问答的文档：{formatted_names}。只有处理成功并处于 READY 状态的 Markdown 文档会进入问答范围。"

    citations = [
        {
            "documentId": document.id,
            "documentName": document.filename,
            "chunkId": f"{document.id}:catalog",
            "headingPath": "知识库目录",
            "excerpt": "该文档当前处理状态为 READY，可参与知识问答。",
        }
        for document in documents
    ]
    return {
        "type": "answer",
        "question": question,
        "answer": answer,
        "citations": citations,
        "checks": {
            "foundEvidence": True,
            "externalKnowledgeUsed": False,
            "citationDocumentCount": len(document_names),
        },
    }


def _evidence_supports_question(question: str, evidence: List[DocumentChunk]) -> bool:
    question_terms = set(_meaningful_term_list(question))
    if not question_terms:
        return False
    return any(question_terms & _chunk_term_set(chunk) for chunk in evidence)


def _vector_recall_size(top_k: int, ready_chunk_count: int) -> int:
    if ready_chunk_count <= 0:
        return max(1, top_k)
    return max(1, min(ready_chunk_count, max(top_k * 3, top_k)))


def _hybrid_rerank(
    question: str,
    vector_evidence: List[DocumentChunk],
    ready_chunks: List[DocumentChunk],
    top_k: int,
) -> List[DocumentChunk]:
    query_terms = set(_meaningful_term_list(question))
    vector_scores = {chunk.id: chunk.score for chunk in vector_evidence}
    candidates = {chunk.id: chunk for chunk in ready_chunks}
    for chunk in vector_evidence:
        candidates.setdefault(chunk.id, chunk)

    if not candidates:
        return []

    document_frequencies = _document_frequencies(candidates.values())
    total_documents = max(1, len(candidates))
    scored: list[DocumentChunk] = []
    for chunk in candidates.values():
        lexical_score = _lexical_relevance_score(
            query_terms,
            chunk,
            document_frequencies,
            total_documents,
        )
        vector_score = vector_scores.get(chunk.id, 0.0)
        if lexical_score <= 0 and vector_score <= 0:
            continue

        if lexical_score > 0:
            combined_score = (lexical_score * 0.72) + (vector_score * 0.28)
            combined_score += min(lexical_score, vector_score) * 0.08
        else:
            combined_score = vector_score * 0.85
        combined_score += _intent_adjustment(question, chunk)
        scored.append(replace(chunk, score=min(1.0, round(combined_score, 4))))

    scored.sort(key=lambda item: (item.score, item.chunk_index * -1), reverse=True)
    return scored[:top_k]


def _lexical_relevance_score(
    query_terms: set[str],
    chunk: DocumentChunk,
    document_frequencies: Dict[str, int],
    total_documents: int,
) -> float:
    if not query_terms:
        return 0.0

    term_weights = _weighted_chunk_terms(chunk)
    if not term_weights:
        return 0.0

    matched_weight = 0.0
    total_weight = 0.0
    density_weight = 0.0
    for term in query_terms:
        idf = math.log((total_documents + 1) / (document_frequencies.get(term, 0) + 0.5)) + 1
        total_weight += idf
        frequency = term_weights.get(term, 0.0)
        if frequency <= 0:
            continue
        matched_weight += idf
        density_weight += idf * min(1.0, 0.45 + math.log1p(frequency) / 2.5)

    if total_weight <= 0 or matched_weight <= 0:
        return 0.0

    coverage = matched_weight / total_weight
    density = density_weight / total_weight
    heading_terms = set(_meaningful_term_list(chunk.heading_path or ""))
    document_terms = set(_meaningful_term_list(chunk.document_name))
    heading_boost = 0.08 if query_terms & heading_terms else 0.0
    document_boost = 0.04 if query_terms & document_terms else 0.0
    return min(1.0, (coverage * 0.72) + (density * 0.20) + heading_boost + document_boost)


def _document_frequencies(chunks: Iterable[DocumentChunk]) -> Dict[str, int]:
    frequencies: Counter[str] = Counter()
    for chunk in chunks:
        frequencies.update(_chunk_term_set(chunk))
    return dict(frequencies)


def _chunk_term_set(chunk: DocumentChunk) -> set[str]:
    return set(_weighted_chunk_terms(chunk))


def _weighted_chunk_terms(chunk: DocumentChunk) -> Dict[str, float]:
    weighted: Dict[str, float] = {}

    def add_terms(text: str, weight: float) -> None:
        for term in _meaningful_term_list(text):
            weighted[term] = weighted.get(term, 0.0) + weight

    add_terms(chunk.text, 1.0)
    if chunk.heading_path:
        add_terms(chunk.heading_path, 1.35)
    add_terms(chunk.document_name, 1.1)
    return weighted


def _intent_adjustment(question: str, chunk: DocumentChunk) -> float:
    question_text = question.lower()
    chunk_text = f"{chunk.heading_path or ''}\n{chunk.text}".lower()
    asks_format = any(keyword in question_text for keyword in ("格式", "扩展名", "类型", "format"))
    if not asks_format:
        return 0.0

    direct_rule = any(
        keyword in chunk_text
        for keyword in ("仅允许", "仅接受", "只支持", "推荐扩展名", ".md", "` .md `")
    )
    boundary_rule = any(keyword in chunk_text for keyword in ("不提供", "非 markdown", "不得进入", "失败"))
    if direct_rule:
        return 0.18
    if boundary_rule:
        return -0.18
    return 0.0


def _meaningful_term_list(text: str) -> List[str]:
    lowered = text.lower()
    terms: list[str] = []
    terms.extend(term for term in re.findall(r"[a-z0-9_]{2,}", lowered) if term not in _STOP_TERMS)
    for span in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        for segment in _split_cjk_span(span):
            if len(segment) <= 8:
                terms.append(segment)
            for width in (2, 3):
                for index in range(max(0, len(segment) - width + 1)):
                    terms.append(segment[index : index + width])
    return _expand_terms(_dedupe_terms(term for term in terms if term not in _STOP_TERMS))


def _split_cjk_span(span: str) -> List[str]:
    normalized = span
    for stop_term in sorted(_STOP_TERMS, key=len, reverse=True):
        normalized = normalized.replace(stop_term, " ")
    normalized = re.sub(r"[的了和与及或是在为对年月日并让它]+", " ", normalized)
    return [segment for segment in normalized.split() if len(segment) >= 2]


def _expand_terms(terms: List[str]) -> List[str]:
    expanded = list(terms)
    for term in terms:
        expanded.extend(_TERM_EXPANSIONS.get(term, []))
    return _dedupe_terms(expanded)


def _dedupe_terms(terms: Iterable[str]) -> List[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped


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
    "文件",
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
    "mvp",
}


_TERM_EXPANSIONS = {
    "格式": ["扩展名", "markdown", "md"],
    "扩展名": ["格式", "markdown", "md"],
    "大模型": ["llm", "模型"],
    "模型": ["llm", "大模型"],
    "问答": ["qa"],
}
