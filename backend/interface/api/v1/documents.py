from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Query, Request, UploadFile

from backend.application.commandsvc.process_document import ProcessDocumentUseCase
from backend.application.commandsvc.upload_markdown_document import (
    UploadMarkdownDocumentUseCase,
)
from backend.application.querysvc.list_documents import KnowledgeBaseQueryService
from backend.shared.errors import NotFoundError

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", status_code=202)
@router.post("/", status_code=202, include_in_schema=False)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict:
    content = await file.read()
    use_case = UploadMarkdownDocumentUseCase(
        request.app.state.settings,
        request.app.state.repository,
        request.app.state.storage,
    )
    result = use_case.execute(
        filename=file.filename or "",
        content=content,
        mime_type=file.content_type or "text/markdown",
    )
    processor = ProcessDocumentUseCase(
        request.app.state.settings,
        request.app.state.repository,
        request.app.state.storage,
        request.app.state.splitter,
        request.app.state.embedding_service,
        request.app.state.vector_store,
    )
    background_tasks.add_task(processor.execute, result.document_id)
    return {
        "documentId": result.document_id,
        "filename": result.filename,
        "status": result.status,
        "message": result.message,
    }


@router.get("")
@router.get("/", include_in_schema=False)
def list_documents(
    request: Request,
    status: str = Query("READY"),
    limit: int = Query(50),
    offset: int = Query(0),
) -> dict:
    return KnowledgeBaseQueryService(request.app.state.repository).documents(
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}")
def get_document(request: Request, document_id: str) -> dict:
    document = request.app.state.repository.get_document(document_id)
    if document is None:
        raise NotFoundError("文档不存在")
    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status.value,
        "failureCode": document.failure_code,
        "failureMessage": document.failure_message,
        "chunkCount": document.chunk_count,
        "createdAt": document.created_at,
        "processedAt": document.processed_at,
    }
