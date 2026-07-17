from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.knowledge.entities import DocumentChunk
from backend.domain.retrieval.services import VectorStore


class ChromaDBEmbeddingService(VectorStore):
    """ChromaDB vector store implementation."""

    def __init__(self, persist_directory: str = "database/vector_db") -> None:
        try:
            import chromadb
        except ModuleNotFoundError as exc:
            raise RuntimeError("缺少 chromadb 依赖，无法启用 Chroma 向量检索") from exc

        self._client = chromadb.PersistentClient(path=persist_directory)

    def save(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        collection = self._collection(collection_name)
        if not ids:
            return
        _validate_payload(ids, embeddings, metadatas, documents)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def upsert_chunks(
        self,
        *,
        collection_name: str,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> None:
        ids = [chunk.id for chunk in chunks]
        metadatas = [
            {
                "documentId": chunk.document_id,
                "documentName": chunk.document_name,
                "chunkIndex": chunk.chunk_index,
                "headingPath": chunk.heading_path or "",
                "status": "READY",
            }
            for chunk in chunks
        ]
        documents = [chunk.text for chunk in chunks]
        self.save(
            collection_name=collection_name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def query_chunks(
        self,
        *,
        collection_name: str,
        query_embedding: List[float],
        top_k: int,
        min_score: float,
    ) -> List[DocumentChunk]:
        collection = self._collection(collection_name)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, top_k),
            where={"status": "READY"},
            include=["metadatas", "documents", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks: list[DocumentChunk] = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] or {}
            score = _distance_to_score(distances[index] if index < len(distances) else None)
            if score < min_score:
                continue
            heading_path = metadata.get("headingPath") or None
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    document_id=str(metadata.get("documentId", "")),
                    document_name=str(metadata.get("documentName", "")),
                    chunk_index=int(metadata.get("chunkIndex", index)),
                    heading_path=heading_path,
                    text=documents[index] or "",
                    token_estimate=max(1, len(documents[index] or "") // 2),
                    score=score,
                )
            )
        return chunks

    def delete_by_document_id(self, *, collection_name: str, document_id: str) -> None:
        collection = self._collection(collection_name)
        existing = collection.get(where={"documentId": document_id}, include=[])
        ids = existing.get("ids") or []
        if ids:
            collection.delete(ids=ids)

    def _collection(self, collection_name: str):
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )


ChromaVectorStore = ChromaDBEmbeddingService


def _validate_payload(
    ids: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, Any]]],
    documents: Optional[List[str]],
) -> None:
    if len(ids) != len(embeddings):
        raise ValueError("ids 与 embeddings 长度必须一致")
    if metadatas is not None and len(metadatas) != len(ids):
        raise ValueError("metadatas 长度必须与 ids 一致")
    if documents is not None and len(documents) != len(ids):
        raise ValueError("documents 长度必须与 ids 一致")


def _distance_to_score(distance: Optional[float]) -> float:
    if distance is None:
        return 0.0
    if distance < 0:
        return 0.0
    return max(0.0, 1.0 - distance)
