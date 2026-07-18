from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Request

from backend.application.querysvc.ask_knowledge_question import AskKnowledgeQuestionUseCase

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


class AskQuestionRequest(BaseModel):
    question: str


@router.post("/ask")
def ask_question(request: Request, payload: AskQuestionRequest) -> dict:
    return AskKnowledgeQuestionUseCase(
        request.app.state.settings,
        request.app.state.repository,
        request.app.state.embedding_service,
        request.app.state.vector_store,
        request.app.state.llm_service,
        request.app.state.llm_log_repository,
    ).execute(payload.question)
