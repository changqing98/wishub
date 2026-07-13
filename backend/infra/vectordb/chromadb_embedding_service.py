from typing import Any, Dict, List, Optional
import chromadb

from backend.domain.domainsvc.embedding import EmbeddingService


class ChromaDBEmbeddingService(EmbeddingService):
    """ChromaDB 向量存储实现。"""

    def __init__(self, persist_directory: str = "database/vector_db") -> None:
        self._client = chromadb.PersistentClient(path=persist_directory)

    def save(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        if not ids:
            return

        if len(ids) != len(embeddings):
            raise ValueError("ids 与 embeddings 长度必须一致")

        if metadatas is not None and len(metadatas) != len(ids):
            raise ValueError("metadatas 长度必须与 ids 一致")

        if documents is not None and len(documents) != len(ids):
            raise ValueError("documents 长度必须与 ids 一致")

        collection = self._client.get_or_create_collection(name=collection_name)

        payload = {
            "ids": ids,
            "embeddings": embeddings,
        }
        if metadatas is not None:
            payload["metadatas"] = metadatas
        if documents is not None:
            payload["documents"] = documents

        collection.upsert(**payload)
