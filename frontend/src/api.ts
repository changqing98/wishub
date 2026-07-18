import {
  ApiError,
  DocumentStatus,
  KnowledgeBaseSummary,
  KnowledgeDocument,
  LLMCallLogList,
  QAResult,
  UploadResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

type DocumentListResponse = {
  readyDocumentCount: number;
  documents: KnowledgeDocument[];
};

export async function fetchSummary(): Promise<KnowledgeBaseSummary> {
  return request("/api/v1/knowledge-base/summary");
}

export async function fetchDocuments(): Promise<DocumentListResponse> {
  return request("/api/v1/documents?status=READY&limit=50&offset=0");
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/v1/documents", {
    method: "POST",
    body: formData,
  });
}

export async function fetchDocumentStatus(documentId: string): Promise<DocumentStatus> {
  return request(`/api/v1/documents/${documentId}`);
}

export async function askQuestion(question: string): Promise<QAResult> {
  return request("/api/v1/qa/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export async function fetchLLMLogs(): Promise<LLMCallLogList> {
  return request("/api/v1/llm-logs?limit=50&offset=0");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload.error || {};
    throw new ApiError(
      error.code || "REQUEST_FAILED",
      error.message || "请求失败，请稍后重试",
      response.status,
    );
  }
  return payload as T;
}
