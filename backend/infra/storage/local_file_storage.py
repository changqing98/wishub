from __future__ import annotations

from pathlib import Path


class LocalFileStorage:
    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def save_markdown(self, document_id: str, content: bytes) -> str:
        path = self._upload_dir / f"{document_id}.md"
        path.write_bytes(content)
        return str(path)

    def read_text(self, storage_path: str) -> str:
        return Path(storage_path).read_text(encoding="utf-8")
