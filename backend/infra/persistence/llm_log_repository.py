from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class LLMCallLogRepository:
    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path
        parent = os.path.dirname(sqlite_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists llm_call_logs (
                    id text primary key,
                    question text not null,
                    model_id text not null default '',
                    status text not null,
                    request_json text not null,
                    response_text text,
                    parsed_response_json text,
                    final_result_json text,
                    error_message text,
                    latency_ms integer not null,
                    created_at text not null
                );

                create index if not exists idx_llm_call_logs_created_at
                on llm_call_logs(created_at);
                """
            )
            _ensure_column(conn, "model_id", "text not null default ''")

    def create(
        self,
        *,
        question: str,
        model_id: str,
        status: str,
        request_payload: Any,
        response_text: Optional[str],
        parsed_response: Optional[Any],
        final_result: Optional[Any],
        error_message: Optional[str],
        latency_ms: int,
    ) -> str:
        log_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                insert into llm_call_logs (
                    id, question, model_id, status, request_json, response_text,
                    parsed_response_json, final_result_json, error_message,
                    latency_ms, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    question,
                    model_id,
                    status,
                    _json_dumps(request_payload),
                    response_text,
                    _json_dumps(parsed_response) if parsed_response is not None else None,
                    _json_dumps(final_result) if final_result is not None else None,
                    error_message,
                    latency_ms,
                    _now(),
                ),
            )
        return log_id

    def list_logs(self, *, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with self._connect() as conn:
            total = int(
                conn.execute("select count(*) as count from llm_call_logs").fetchone()["count"]
            )
            rows = conn.execute(
                """
                select *
                from llm_call_logs
                order by created_at desc
                limit ? offset ?
                """,
                (limit, offset),
            ).fetchall()
        return {
            "total": total,
            "logs": [_row_to_dict(row) for row in rows],
        }


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "question": row["question"],
        "modelId": row["model_id"] or "unknown",
        "status": row["status"],
        "request": _json_loads(row["request_json"]),
        "responseText": row["response_text"],
        "parsedResponse": _json_loads(row["parsed_response_json"]),
        "finalResult": _json_loads(row["final_result_json"]),
        "errorMessage": row["error_message"],
        "latencyMs": int(row["latency_ms"]),
        "createdAt": row["created_at"],
    }


def _ensure_column(conn: sqlite3.Connection, column_name: str, column_definition: str) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("pragma table_info(llm_call_logs)").fetchall()
    }
    if column_name not in existing_columns:
        conn.execute(f"alter table llm_call_logs add column {column_name} {column_definition}")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_loads(value: Optional[str]) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
