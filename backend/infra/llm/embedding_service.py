from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, List, Optional

from backend.domain.retrieval.services import TextEmbeddingService


class HashEmbeddingService(TextEmbeddingService):
    """Deterministic local embedding for development and tests.

    It keeps the production pipeline shape as Embedding -> Chroma without
    requiring a model download or external API key.
    """

    def __init__(self, dimension: int = 256) -> None:
        self._dimension = dimension

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self._dimension
        for token in _tokens(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbeddingService(TextEmbeddingService):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        if not model or not api_key:
            raise ValueError("EMBEDDING_MODEL 和 EMBEDDING_API_KEY/LLM_API_KEY 必须配置")

        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("缺少 openai 依赖，无法启用真实 Embedding 服务") from exc

        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout)

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        text_list = list(texts)
        if not text_list:
            return []
        response = self._client.embeddings.create(model=self._model, input=text_list)
        return [list(item.embedding) for item in response.data]


class SentenceTransformerEmbeddingService(TextEmbeddingService):
    """Real local semantic embedding backed by sentence-transformers."""

    def __init__(
        self,
        *,
        model: str,
        device: Optional[str] = None,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        query_instruction: Optional[str] = None,
    ) -> None:
        if not model:
            raise ValueError("EMBEDDING_MODEL 必须配置")

        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise RuntimeError("缺少 sentence-transformers 依赖，无法启用真实 Embedding 服务") from exc

        self._model_name = model
        self._model = SentenceTransformer(model, device=device)
        self._batch_size = max(1, batch_size)
        self._normalize_embeddings = normalize_embeddings
        self._query_instruction = query_instruction or _default_query_instruction(model)

    def embed_query(self, text: str) -> List[float]:
        return self._embed([_apply_query_instruction(text, self._query_instruction)])[0]

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        text_list = list(texts)
        if not text_list:
            return []
        return self._embed(text_list)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype(float).tolist()


def _default_query_instruction(model: str) -> str:
    normalized = model.lower()
    if "bge" in normalized and "zh" in normalized:
        return "为这个句子生成表示以用于检索相关文章："
    if "bge" in normalized:
        return "Represent this sentence for searching relevant passages: "
    return ""


def _apply_query_instruction(text: str, instruction: str) -> str:
    text = text or ""
    if not instruction:
        return text
    return f"{instruction}{text}"


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    result: set[str] = set(re.findall(r"[a-z0-9_]{2,}", lowered))
    for span in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        if len(span) <= 8:
            result.add(span)
        for width in (2, 3):
            for index in range(max(0, len(span) - width + 1)):
                result.add(span[index : index + width])
    return result
