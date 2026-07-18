from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    sqlite_path: str = "database/wishub.sqlite3"
    upload_dir: str = "database/uploads"
    chroma_path: str = "database/chroma_db"
    chroma_collection: str = "wishub_mvp_documents_sentence_transformers"
    max_markdown_bytes: int = 5 * 1024 * 1024
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.25
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimension: int = 256
    embedding_device: str = ""
    embedding_batch_size: int = 32
    embedding_query_instruction: str = ""
    llm_provider: str = "auto"
    llm_model_id: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_timeout: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            sqlite_path=os.getenv("WISHUB_SQLITE_PATH", cls.sqlite_path),
            upload_dir=os.getenv("WISHUB_UPLOAD_DIR", cls.upload_dir),
            chroma_path=os.getenv("WISHUB_CHROMA_PATH", cls.chroma_path),
            chroma_collection=os.getenv(
                "WISHUB_CHROMA_COLLECTION", cls.chroma_collection
            ),
            max_markdown_bytes=int(
                os.getenv("WISHUB_MAX_MARKDOWN_BYTES", str(cls.max_markdown_bytes))
            ),
            retrieval_top_k=int(os.getenv("WISHUB_RETRIEVAL_TOP_K", str(cls.retrieval_top_k))),
            retrieval_min_score=float(
                os.getenv("WISHUB_RETRIEVAL_MIN_SCORE", str(cls.retrieval_min_score))
            ),
            embedding_provider=os.getenv(
                "WISHUB_EMBEDDING_PROVIDER", cls.embedding_provider
            ),
            embedding_model=os.getenv("EMBEDDING_MODEL", cls.embedding_model),
            embedding_api_key=os.getenv(
                "EMBEDDING_API_KEY", os.getenv("LLM_API_KEY", cls.embedding_api_key)
            ),
            embedding_base_url=os.getenv(
                "EMBEDDING_BASE_URL", os.getenv("LLM_BASE_URL", cls.embedding_base_url)
            ),
            embedding_dimension=int(
                os.getenv("WISHUB_EMBEDDING_DIMENSION", str(cls.embedding_dimension))
            ),
            embedding_device=os.getenv("WISHUB_EMBEDDING_DEVICE", cls.embedding_device),
            embedding_batch_size=int(
                os.getenv("WISHUB_EMBEDDING_BATCH_SIZE", str(cls.embedding_batch_size))
            ),
            embedding_query_instruction=os.getenv(
                "WISHUB_EMBEDDING_QUERY_INSTRUCTION", cls.embedding_query_instruction
            ),
            llm_provider=os.getenv("WISHUB_LLM_PROVIDER", cls.llm_provider),
            llm_model_id=os.getenv("LLM_MODEL_ID", cls.llm_model_id),
            llm_api_key=os.getenv("LLM_API_KEY", cls.llm_api_key),
            llm_base_url=os.getenv("LLM_BASE_URL", cls.llm_base_url),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", str(cls.llm_timeout))),
        )
