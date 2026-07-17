from __future__ import annotations

from fastapi import APIRouter, Request

from backend.application.querysvc.list_documents import KnowledgeBaseQueryService

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])


@router.get("/summary")
def get_summary(request: Request) -> dict:
    return KnowledgeBaseQueryService(request.app.state.repository).summary()
