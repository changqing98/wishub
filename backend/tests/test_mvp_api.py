from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.shared.config import Settings


def make_client(tmp_path) -> TestClient:
    settings = Settings(
        sqlite_path=str(tmp_path / "wishub.sqlite3"),
        upload_dir=str(tmp_path / "uploads"),
        chroma_path=str(tmp_path / "chroma"),
        chroma_collection="wishub_test_documents",
        retrieval_min_score=0.25,
    )
    return TestClient(create_app(settings))


def test_empty_summary_and_empty_qa(tmp_path) -> None:
    client = make_client(tmp_path)

    summary = client.get("/api/v1/knowledge-base/summary")
    assert summary.status_code == 200
    assert summary.json()["readyDocumentCount"] == 0
    assert summary.json()["status"] == "EMPTY"

    qa = client.post("/api/v1/qa/ask", json={"question": "如何上传文档？"})
    assert qa.status_code == 200
    assert qa.json()["type"] == "empty_knowledge_base"


def test_upload_validation(tmp_path) -> None:
    client = make_client(tmp_path)

    non_markdown = client.post(
        "/api/v1/documents",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert non_markdown.status_code == 400
    assert non_markdown.json()["error"]["code"] == "ONLY_MARKDOWN_SUPPORTED"

    empty_markdown = client.post(
        "/api/v1/documents",
        files={"file": ("empty.md", b"  \n", "text/markdown")},
    )
    assert empty_markdown.status_code == 400
    assert empty_markdown.json()["error"]["code"] == "EMPTY_MARKDOWN_FILE"


def test_upload_ready_summary_list_and_duplicate(tmp_path) -> None:
    client = make_client(tmp_path)

    response = upload_fixture(client)
    document_id = response["documentId"]

    status = client.get(f"/api/v1/documents/{document_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "READY"
    assert status.json()["chunkCount"] > 0

    summary = client.get("/api/v1/knowledge-base/summary").json()
    assert summary["readyDocumentCount"] == 1
    assert summary["status"] == "READY"

    documents = client.get("/api/v1/documents").json()
    assert documents["readyDocumentCount"] == 1
    assert documents["documents"][0]["filename"] == "产品使用指南.md"

    duplicate = client.post(
        "/api/v1/documents",
        files={"file": ("产品使用指南.md", fixture_markdown().encode("utf-8"), "text/markdown")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_DOCUMENT_NAME"


def test_strict_qa_answer_refusal_and_clarification(tmp_path) -> None:
    client = make_client(tmp_path)
    upload_fixture(client)

    answer = client.post(
        "/api/v1/qa/ask",
        json={"question": "如何上传一个 Markdown 文档并让它参与问答？"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["type"] == "answer"
    assert payload["checks"]["externalKnowledgeUsed"] is False
    assert payload["citations"][0]["documentName"] == "产品使用指南.md"
    assert "上传" in payload["answer"]

    refusal = client.post("/api/v1/qa/ask", json={"question": "明天天气怎么样？"})
    assert refusal.status_code == 200
    assert refusal.json()["type"] == "refusal"

    clarification = client.post("/api/v1/qa/ask", json={"question": "怎么做"})
    assert clarification.status_code == 200
    assert clarification.json()["type"] == "clarification"


def upload_fixture(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "产品使用指南.md",
                fixture_markdown().encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "PROCESSING"
    return response.json()


def fixture_markdown() -> str:
    return """# 上传与入库

用户进入知识库页面，选择一个 Markdown 文件上传。
文件解析和索引完成后，文档才会进入有效目录并参与知识问答。

# 边界规则

知识库没有相关依据时，系统会明确拒答，不调用外部搜索或常识补全。
"""
