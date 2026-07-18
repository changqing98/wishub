from __future__ import annotations

import json
import re
from typing import Any, Dict, Generator, Iterable, List, Union

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

        selected_units = _select_relevant_units(question, evidence)
        if not selected_units:
            selected_units = _fallback_units(evidence)
        if not selected_units:
            return json.dumps(
                {
                    "type": "refusal",
                    "message": "当前知识库暂无相关依据",
                    "detail": "这个问题无法从当前知识库中的 Markdown 文档确认。你可以换一种问法，或补充更具体的关键词。",
                    "citations": [],
                },
                ensure_ascii=False,
            )

        primary = selected_units[0]
        answer_text = "；".join(unit["text"] for unit in selected_units)
        cited_chunk_ids = _dedupe(str(unit["chunkId"]) for unit in selected_units if unit.get("chunkId"))

        return json.dumps(
            {
                "type": "answer",
                "answer": f"根据《{primary.get('documentName')}》，{answer_text}",
                "citations": [{"chunkId": chunk_id} for chunk_id in cited_chunk_ids],
            },
            ensure_ascii=False,
        )


def _select_relevant_units(question: str, evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    question_terms = set(_terms(question))
    if not question_terms:
        return []

    scored_units: list[tuple[float, int, Dict[str, Any]]] = []
    for evidence_index, item in enumerate(evidence):
        context_terms = set(_terms(str(item.get("headingPath") or "")))
        for unit_index, unit_text in enumerate(_split_units(str(item.get("text") or ""))):
            unit_terms = set(_terms(unit_text)) | context_terms
            overlap = question_terms & unit_terms
            if not overlap:
                continue
            coverage = len(overlap) / max(len(question_terms), 1)
            if coverage < 0.3:
                continue
            score = coverage + (float(item.get("score") or 0) * 0.12)
            scored_units.append(
                (
                    score,
                    (evidence_index * 100) + unit_index,
                    {
                        "chunkId": item.get("chunkId"),
                        "documentName": item.get("documentName"),
                        "text": _excerpt(_clean_unit(unit_text), 220),
                    },
                )
            )

    scored_units.sort(key=lambda unit: (unit[0], -unit[1]), reverse=True)
    if _asks_format(question):
        direct_format_units = [
            unit for unit in scored_units if _is_direct_format_unit(unit[2]["text"])
        ]
        selected_units = direct_format_units[:2] if direct_format_units else scored_units[:3]
    else:
        selected_units = scored_units[:3]
    selected_units.sort(key=lambda unit: unit[1])
    return [unit for _, _, unit in selected_units]


def _asks_format(question: str) -> bool:
    lowered = question.lower()
    return any(keyword in lowered for keyword in ("格式", "扩展名", "类型", "format"))


def _is_direct_format_unit(text: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("本地扩展名或后端校验失败", "展示“仅支持", "展示\"仅支持")):
        return False
    if lowered.startswith("非 markdown"):
        return False
    mentions_format = ".md" in lowered or "markdown" in lowered
    direct_rule = any(
        keyword in lowered
        for keyword in ("仅允许", "仅接受", "只支持", "推荐扩展名", "扩展名")
    )
    return mentions_format and direct_rule


def _fallback_units(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    units: list[Dict[str, Any]] = []
    for item in evidence[:2]:
        text_units = _split_units(str(item.get("text") or ""))
        if not text_units:
            continue
        units.append(
            {
                "chunkId": item.get("chunkId"),
                "documentName": item.get("documentName"),
                "text": _excerpt(_clean_unit(text_units[0]), 220),
            }
        )
    return units


def _split_units(text: str) -> List[str]:
    units: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("|"):
            units.append(clean)
            continue
        units.extend(part for part in re.split(r"(?<=[。！？；])\s*", clean) if part.strip())
    return units


def _clean_unit(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text)
    text = text.replace("|", "；")
    return re.sub(r"\s+", " ", text).strip("； ")


def _terms(text: str) -> List[str]:
    lowered = text.lower()
    terms: list[str] = []
    terms.extend(term for term in re.findall(r"[a-z0-9_]{2,}", lowered) if term not in _STOP_TERMS)
    for span in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        normalized = span
        for stop_term in sorted(_STOP_TERMS, key=len, reverse=True):
            normalized = normalized.replace(stop_term, " ")
        normalized = re.sub(r"[的了和与及或是在为对年月日并让它]+", " ", normalized)
        for segment in normalized.split():
            if len(segment) < 2:
                continue
            terms.append(segment)
            for width in (2, 3):
                for index in range(max(0, len(segment) - width + 1)):
                    terms.append(segment[index : index + width])
    return _expand_terms(_dedupe(term for term in terms if term not in _STOP_TERMS))


def _expand_terms(terms: List[str]) -> List[str]:
    expanded = list(terms)
    for term in terms:
        expanded.extend(_TERM_EXPANSIONS.get(term, []))
    return _dedupe(expanded)


def _dedupe(values: Iterable[str]) -> List[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _excerpt(text: str, max_length: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


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
