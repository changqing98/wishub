from __future__ import annotations

import uuid
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.domain.domainsvc.llm_service import LLMService
from backend.domain.retrieval.services import TextEmbeddingService, VectorStore
from backend.infra.persistence.document_repository import DocumentRepository
from backend.infra.service_factory import (
    build_embedding_service,
    build_llm_service,
    build_vector_store,
)
from backend.infra.spliter.markdown_spliter import MarkdownSplitter
from backend.infra.storage.local_file_storage import LocalFileStorage
from backend.interface.api.v1 import documents, knowledge_base, qa
from backend.shared.config import Settings
from backend.shared.errors import AppError


def create_app(
    settings: Optional[Settings] = None,
    embedding_service: Optional[TextEmbeddingService] = None,
    vector_store: Optional[VectorStore] = None,
    llm_service: Optional[LLMService] = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="wishub MVP API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.repository = DocumentRepository(settings.sqlite_path)
    app.state.storage = LocalFileStorage(settings.upload_dir)
    app.state.splitter = MarkdownSplitter()
    app.state.embedding_service = embedding_service or build_embedding_service(settings)
    app.state.vector_store = vector_store or build_vector_store(settings)
    app.state.llm_service = llm_service or build_llm_service(settings)

    app.include_router(knowledge_base.router)
    app.include_router(documents.router)
    app.include_router(qa.router)

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "traceId": str(uuid.uuid4()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        del exc
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "服务暂时不可用",
                    "traceId": str(uuid.uuid4()),
                }
            },
        )

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
