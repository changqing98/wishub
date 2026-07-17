from __future__ import annotations

from backend.domain.domainsvc.llm_service import LLMService
from backend.domain.retrieval.services import TextEmbeddingService, VectorStore
from backend.infra.llm.embedding_service import HashEmbeddingService, OpenAIEmbeddingService
from backend.infra.llm.evidence_bound_llm_service import EvidenceBoundLLMService
from backend.infra.llm.llm_service_openai import OpenAICompatibleLLMService
from backend.infra.vectordb.chromadb_embedding_service import ChromaVectorStore
from backend.shared.config import Settings


def build_embedding_service(settings: Settings) -> TextEmbeddingService:
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        return OpenAIEmbeddingService(
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            timeout=settings.llm_timeout,
        )
    if provider == "hash":
        return HashEmbeddingService(dimension=settings.embedding_dimension)
    raise ValueError(f"不支持的 Embedding provider: {settings.embedding_provider}")


def build_llm_service(settings: Settings) -> LLMService:
    provider = settings.llm_provider.lower()
    can_use_openai = bool(settings.llm_model_id and settings.llm_api_key)
    if provider == "openai" or (provider == "auto" and can_use_openai):
        return OpenAICompatibleLLMService(
            model=settings.llm_model_id,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout,
        )
    if provider in {"auto", "offline"}:
        return EvidenceBoundLLMService()
    raise ValueError(f"不支持的 LLM provider: {settings.llm_provider}")


def build_vector_store(settings: Settings) -> VectorStore:
    return ChromaVectorStore(persist_directory=settings.chroma_path)
