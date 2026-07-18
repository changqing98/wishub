from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/v1/llm-logs", tags=["llm-logs"])


@router.get("")
@router.get("/", include_in_schema=False)
def list_llm_logs(
    request: Request,
    limit: int = Query(50),
    offset: int = Query(0),
) -> dict:
    return request.app.state.llm_log_repository.list_logs(limit=limit, offset=offset)
