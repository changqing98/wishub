from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DocumentStatus(str, Enum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Document:
    id: str
    filename: str
    storage_path: str
    content_sha256: str
    size_bytes: int
    mime_type: str
    status: DocumentStatus
    failure_code: Optional[str]
    failure_message: Optional[str]
    chunk_count: int
    created_at: str
    updated_at: str
    processed_at: Optional[str]


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    document_id: str
    document_name: str
    chunk_index: int
    heading_path: Optional[str]
    text: str
    token_estimate: int
    score: float = 0
