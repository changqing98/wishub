from __future__ import annotations

import pytest

pytest.importorskip("chromadb")

from backend.domain.knowledge.entities import DocumentChunk
from backend.infra.vectordb import ChromaDBEmbeddingService


def test_save_and_query_chunks(tmp_path):
    svc = ChromaDBEmbeddingService(persist_directory=str(tmp_path / "chroma"))
    collection = "test_collection"
    chunks = [
        DocumentChunk(
            id="doc-1:0",
            document_id="doc-1",
            document_name="产品使用指南.md",
            chunk_index=0,
            heading_path="上传与入库",
            text="用户进入知识库页面，选择一个 Markdown 文件上传。",
            token_estimate=20,
        )
    ]

    svc.upsert_chunks(
        collection_name=collection,
        chunks=chunks,
        embeddings=[[1.0, 0.0, 0.0]],
    )
    result = svc.query_chunks(
        collection_name=collection,
        query_embedding=[1.0, 0.0, 0.0],
        top_k=1,
        min_score=0.8,
    )

    assert result[0].id == "doc-1:0"
    assert result[0].document_name == "产品使用指南.md"
