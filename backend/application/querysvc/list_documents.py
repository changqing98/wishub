from __future__ import annotations

from backend.infra.persistence.document_repository import DocumentRepository


class KnowledgeBaseQueryService:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    def summary(self) -> dict:
        ready_count = self._repository.ready_count()
        processing_count = self._repository.processing_count()
        if processing_count > 0:
            status = "PROCESSING"
        elif ready_count > 0:
            status = "READY"
        else:
            status = "EMPTY"
        return {
            "readyDocumentCount": ready_count,
            "status": status,
            "boundaryText": "回答只来自已处理成功的 Markdown 文档，不调用外部搜索或常识补全。",
        }

    def documents(self, *, status: str = "READY", limit: int = 50, offset: int = 0) -> dict:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        return {
            "readyDocumentCount": self._repository.ready_count(),
            "documents": [
                {
                    "id": document.id,
                    "filename": document.filename,
                    "sizeBytes": document.size_bytes,
                    "status": document.status.value,
                    "chunkCount": document.chunk_count,
                    "processedAt": document.processed_at,
                }
                for document in self._repository.list_documents(
                    status=status, limit=limit, offset=offset
                )
            ],
        }
