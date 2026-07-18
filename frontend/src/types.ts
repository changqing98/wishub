export type KnowledgeBaseSummary = {
  readyDocumentCount: number;
  status: "EMPTY" | "READY" | "PROCESSING";
  boundaryText: string;
};

export type KnowledgeDocument = {
  id: string;
  filename: string;
  sizeBytes: number;
  status: "PROCESSING" | "READY" | "FAILED";
  chunkCount: number;
  processedAt: string | null;
};

export type DocumentStatus = {
  id: string;
  filename: string;
  status: "PROCESSING" | "READY" | "FAILED";
  failureCode: string | null;
  failureMessage: string | null;
  chunkCount: number;
  createdAt: string;
  processedAt: string | null;
};

export type UploadResponse = {
  documentId: string;
  filename: string;
  status: "PROCESSING";
  message: string;
};

export type Citation = {
  documentId: string;
  documentName: string;
  chunkId: string;
  headingPath: string | null;
  excerpt: string;
};

export type QAResult =
  | {
      type: "answer";
      question: string;
      answer: string;
      citations: Citation[];
      checks: {
        foundEvidence: boolean;
        externalKnowledgeUsed: boolean;
        citationDocumentCount: number;
      };
    }
  | {
      type: "refusal" | "clarification" | "empty_knowledge_base";
      message: string;
      detail: string;
      citations?: Citation[];
    };

export type LLMCallLog = {
  id: string;
  question: string;
  modelId: string;
  status: "SUCCESS" | "FAILED";
  request: unknown;
  responseText: string | null;
  parsedResponse: unknown | null;
  finalResult: unknown | null;
  errorMessage: string | null;
  latencyMs: number;
  createdAt: string;
};

export type LLMCallLogList = {
  total: number;
  logs: LLMCallLog[];
};

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}
