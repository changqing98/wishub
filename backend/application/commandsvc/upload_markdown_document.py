from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass

from backend.infra.persistence.document_repository import DocumentRepository
from backend.infra.storage.local_file_storage import LocalFileStorage
from backend.shared.config import Settings
from backend.shared.errors import AppError


@dataclass(frozen=True)
class UploadResult:
    document_id: str
    filename: str
    status: str
    message: str


class UploadMarkdownDocumentUseCase:
    def __init__(
        self,
        settings: Settings,
        repository: DocumentRepository,
        storage: LocalFileStorage,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._storage = storage

    def execute(self, *, filename: str, content: bytes, mime_type: str) -> UploadResult:
        safe_filename = os.path.basename(filename or "").strip()
        if not safe_filename.lower().endswith(".md"):
            raise AppError("ONLY_MARKDOWN_SUPPORTED", "仅支持 Markdown 文件（.md）", 400)

        if len(content) > self._settings.max_markdown_bytes:
            raise AppError("FILE_TOO_LARGE", "文件超出大小限制", 413)

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError("MARKDOWN_PARSE_FAILED", "无法按 UTF-8 解析 Markdown 内容", 400) from exc

        if not text.strip():
            raise AppError("EMPTY_MARKDOWN_FILE", "Markdown 内容为空", 400)

        if self._repository.filename_exists(safe_filename):
            raise AppError("DUPLICATE_DOCUMENT_NAME", "已存在同名文档", 409)

        document_id = str(uuid.uuid4())
        storage_path = self._storage.save_markdown(document_id, content)
        self._repository.create_document(
            document_id=document_id,
            filename=safe_filename,
            storage_path=storage_path,
            content_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            mime_type=mime_type or "text/markdown",
        )

        return UploadResult(
            document_id=document_id,
            filename=safe_filename,
            status="PROCESSING",
            message="文件已上传，正在解析和建立检索索引。",
        )
