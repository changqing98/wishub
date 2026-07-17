from __future__ import annotations

from typing import Optional

from backend.domain.knowledge.entities import DocumentChunk
from backend.domain.retrieval.services import TextEmbeddingService, VectorStore
from backend.infra.persistence.document_repository import DocumentRepository
from backend.infra.spliter.markdown_spliter import MarkdownSplitter
from backend.infra.storage.local_file_storage import LocalFileStorage
from backend.shared.config import Settings


class ProcessDocumentUseCase:
    def __init__(
        self,
        settings: Settings,
        repository: DocumentRepository,
        storage: LocalFileStorage,
        splitter: MarkdownSplitter,
        embedding_service: TextEmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._storage = storage
        self._splitter = splitter
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    def execute(self, document_id: str) -> None:
        document = self._repository.get_document(document_id)
        if document is None:
            return

        chunks: Optional[list[DocumentChunk]] = None
        try:
            markdown_text = self._storage.read_text(document.storage_path)
            split_chunks = self._splitter.split(markdown_text)
            if not split_chunks:
                self._repository.mark_failed(
                    document_id,
                    "MARKDOWN_PARSE_FAILED",
                    "无法解析该 Markdown 内容，请检查文件后重试",
                )
                return

            chunks = [
                DocumentChunk(
                    id=f"{document_id}:{index}",
                    document_id=document_id,
                    document_name=document.filename,
                    chunk_index=index,
                    heading_path=chunk.heading_path,
                    text=chunk.text,
                    token_estimate=chunk.token_estimate,
                )
                for index, chunk in enumerate(split_chunks)
            ]
        except Exception:
            self._repository.mark_failed(
                document_id,
                "MARKDOWN_PARSE_FAILED",
                "无法解析该 Markdown 内容，请检查文件后重试",
            )
            return

        try:
            embeddings = self._embedding_service.embed_documents([chunk.text for chunk in chunks])
        except Exception:
            self._repository.mark_failed(
                document_id,
                "EMBEDDING_FAILED",
                "建立检索索引失败，请重试",
            )
            return

        try:
            self._vector_store.delete_by_document_id(
                collection_name=self._settings.chroma_collection,
                document_id=document_id,
            )
            self._vector_store.upsert_chunks(
                collection_name=self._settings.chroma_collection,
                chunks=chunks,
                embeddings=embeddings,
            )
            self._repository.mark_ready(document_id, chunks)
        except Exception:
            self._safe_delete_vectors(document_id)
            self._repository.mark_failed(
                document_id,
                "VECTOR_STORE_FAILED",
                "知识入库失败，请重试",
            )

    def _safe_delete_vectors(self, document_id: str) -> None:
        try:
            self._vector_store.delete_by_document_id(
                collection_name=self._settings.chroma_collection,
                document_id=document_id,
            )
        except Exception:
            return
