from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class MarkdownChunk:
    heading_path: Optional[str]
    text: str
    token_estimate: int


class MarkdownSplitter:
    def __init__(self, chunk_size: int = 900, overlap: int = 120) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def split(self, markdown_text: str) -> List[MarkdownChunk]:
        normalized = self._normalize(markdown_text)
        if not normalized:
            return []

        blocks = self._blocks_with_headings(normalized)
        chunks: List[MarkdownChunk] = []
        for heading_path, text in blocks:
            for piece in self._split_long_text(text):
                clean = piece.strip()
                if clean:
                    chunks.append(
                        MarkdownChunk(
                            heading_path=heading_path,
                            text=clean,
                            token_estimate=max(1, len(clean) // 2),
                        )
                    )
        return chunks

    def _normalize(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _blocks_with_headings(self, text: str) -> List[tuple[Optional[str], str]]:
        heading_stack: list[tuple[int, str]] = []
        current_lines: list[str] = []
        current_heading: Optional[str] = None
        blocks: List[tuple[Optional[str], str]] = []

        for line in text.splitlines():
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading:
                self._append_block(blocks, current_heading, current_lines)
                current_lines = []
                level = len(heading.group(1))
                title = heading.group(2).strip()
                heading_stack = [(l, t) for l, t in heading_stack if l < level]
                heading_stack.append((level, title))
                current_heading = " / ".join(title for _, title in heading_stack)
                continue
            current_lines.append(line)

        self._append_block(blocks, current_heading, current_lines)
        return blocks

    def _append_block(
        self,
        blocks: List[tuple[Optional[str], str]],
        heading_path: Optional[str],
        lines: list[str],
    ) -> None:
        text = "\n".join(lines).strip()
        if text:
            blocks.append((heading_path, text))

    def _split_long_text(self, text: str) -> List[str]:
        if len(text) <= self._chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self._chunk_size)
            split_at = self._best_split_point(text, start, end)
            chunks.append(text[start:split_at])
            if split_at >= len(text):
                break
            start = max(split_at - self._overlap, start + 1)
        return chunks

    def _best_split_point(self, text: str, start: int, end: int) -> int:
        window = text[start:end]
        for delimiter in ("\n\n", "。", "！", "？", "\n"):
            idx = window.rfind(delimiter)
            if idx >= int(len(window) * 0.5):
                return start + idx + len(delimiter)
        return end
