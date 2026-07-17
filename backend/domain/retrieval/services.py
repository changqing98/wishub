from __future__ import annotations

from typing import Iterable, List, Protocol

from backend.domain.knowledge.entities import DocumentChunk


class TextEmbeddingService(Protocol):
    def embed_query(self, text: str) -> List[float]:
        ...

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        ...


class VectorStore(Protocol):
    def upsert_chunks(
        self,
        *,
        collection_name: str,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> None:
        ...

    def query_chunks(
        self,
        *,
        collection_name: str,
        query_embedding: List[float],
        top_k: int,
        min_score: float,
    ) -> List[DocumentChunk]:
        ...

    def delete_by_document_id(self, *, collection_name: str, document_id: str) -> None:
        ...
