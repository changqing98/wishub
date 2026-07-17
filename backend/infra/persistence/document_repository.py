from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from backend.domain.knowledge.entities import Document, DocumentChunk, DocumentStatus


class DocumentRepository:
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
                create table if not exists documents (
                    id text primary key,
                    filename text not null unique,
                    storage_path text not null,
                    content_sha256 text not null,
                    size_bytes integer not null,
                    mime_type text not null,
                    status text not null,
                    failure_code text,
                    failure_message text,
                    chunk_count integer not null default 0,
                    created_at text not null,
                    updated_at text not null,
                    processed_at text
                );

                create index if not exists idx_documents_status_updated_at
                on documents(status, updated_at);

                create index if not exists idx_documents_sha256
                on documents(content_sha256);

                create table if not exists document_chunks (
                    id text primary key,
                    document_id text not null,
                    chunk_index integer not null,
                    heading_path text,
                    text text not null,
                    token_estimate integer not null,
                    created_at text not null,
                    foreign key(document_id) references documents(id)
                );

                create index if not exists idx_document_chunks_document_id
                on document_chunks(document_id);
                """
            )

    def create_document(
        self,
        *,
        document_id: str,
        filename: str,
        storage_path: str,
        content_sha256: str,
        size_bytes: int,
        mime_type: str,
    ) -> Document:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into documents (
                    id, filename, storage_path, content_sha256, size_bytes, mime_type,
                    status, failure_code, failure_message, chunk_count,
                    created_at, updated_at, processed_at
                ) values (?, ?, ?, ?, ?, ?, ?, null, null, 0, ?, ?, null)
                """,
                (
                    document_id,
                    filename,
                    storage_path,
                    content_sha256,
                    size_bytes,
                    mime_type or "text/markdown",
                    DocumentStatus.PROCESSING.value,
                    now,
                    now,
                ),
            )
        document = self.get_document(document_id)
        assert document is not None
        return document

    def filename_exists(self, filename: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "select 1 from documents where filename = ? limit 1", (filename,)
            ).fetchone()
        return row is not None

    def get_document(self, document_id: str) -> Optional[Document]:
        with self._connect() as conn:
            row = conn.execute(
                "select * from documents where id = ?", (document_id,)
            ).fetchone()
        return _document_from_row(row) if row else None

    def list_documents(
        self,
        *,
        status: str = DocumentStatus.READY.value,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Document]:
        sql = "select * from documents"
        params: list[object] = []
        if status != "ALL":
            sql += " where status = ?"
            params.append(status)
        sql += " order by updated_at desc limit ? offset ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_document_from_row(row) for row in rows]

    def ready_count(self) -> int:
        return self._count_by_status(DocumentStatus.READY)

    def processing_count(self) -> int:
        return self._count_by_status(DocumentStatus.PROCESSING)

    def _count_by_status(self, status: DocumentStatus) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "select count(*) as count from documents where status = ?", (status.value,)
            ).fetchone()
        return int(row["count"])

    def mark_ready(self, document_id: str, chunks: Iterable[DocumentChunk]) -> None:
        chunk_list = list(chunks)
        now = _now()
        with self._connect() as conn:
            conn.execute("delete from document_chunks where document_id = ?", (document_id,))
            conn.executemany(
                """
                insert into document_chunks (
                    id, document_id, chunk_index, heading_path, text, token_estimate, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        document_id,
                        chunk.chunk_index,
                        chunk.heading_path,
                        chunk.text,
                        chunk.token_estimate,
                        now,
                    )
                    for chunk in chunk_list
                ],
            )
            conn.execute(
                """
                update documents
                set status = ?, failure_code = null, failure_message = null,
                    chunk_count = ?, updated_at = ?, processed_at = ?
                where id = ?
                """,
                (DocumentStatus.READY.value, len(chunk_list), now, now, document_id),
            )

    def mark_failed(self, document_id: str, failure_code: str, failure_message: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute("delete from document_chunks where document_id = ?", (document_id,))
            conn.execute(
                """
                update documents
                set status = ?, failure_code = ?, failure_message = ?,
                    chunk_count = 0, updated_at = ?, processed_at = ?
                where id = ?
                """,
                (
                    DocumentStatus.FAILED.value,
                    failure_code,
                    failure_message,
                    now,
                    now,
                    document_id,
                ),
            )

    def list_ready_chunks(self) -> List[DocumentChunk]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    c.id,
                    c.document_id,
                    d.filename as document_name,
                    c.chunk_index,
                    c.heading_path,
                    c.text,
                    c.token_estimate
                from document_chunks c
                join documents d on d.id = c.document_id
                where d.status = ?
                order by d.updated_at desc, c.chunk_index asc
                """,
                (DocumentStatus.READY.value,),
            ).fetchall()
        return [
            DocumentChunk(
                id=row["id"],
                document_id=row["document_id"],
                document_name=row["document_name"],
                chunk_index=int(row["chunk_index"]),
                heading_path=row["heading_path"],
                text=row["text"],
                token_estimate=int(row["token_estimate"]),
            )
            for row in rows
        ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _document_from_row(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        filename=row["filename"],
        storage_path=row["storage_path"],
        content_sha256=row["content_sha256"],
        size_bytes=int(row["size_bytes"]),
        mime_type=row["mime_type"],
        status=DocumentStatus(row["status"]),
        failure_code=row["failure_code"],
        failure_message=row["failure_message"],
        chunk_count=int(row["chunk_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        processed_at=row["processed_at"],
    )
