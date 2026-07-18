import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  askQuestion,
  fetchLLMLogs,
  fetchDocumentStatus,
  fetchDocuments,
  fetchSummary,
  uploadDocument,
} from "./api";
import { ApiError, KnowledgeBaseSummary, KnowledgeDocument, LLMCallLog, QAResult } from "./types";

type Page = "knowledge" | "qa" | "logs";
type LoadState = "idle" | "loading" | "ready" | "error";
type UploadState = "idle" | "selected" | "uploading" | "processing" | "success" | "error";

const emptySummary: KnowledgeBaseSummary = {
  readyDocumentCount: 0,
  status: "EMPTY",
  boundaryText: "回答只来自已处理成功的 Markdown 文档，不调用外部搜索或常识补全。",
};

function App() {
  const [page, setPage] = useState<Page>("knowledge");
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [summary, setSummary] = useState<KnowledgeBaseSummary>(emptySummary);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);

  const reload = useCallback(async () => {
    setLoadState("loading");
    setLoadError("");
    try {
      const [summaryResponse, documentsResponse] = await Promise.all([
        fetchSummary(),
        fetchDocuments(),
      ]);
      setSummary(summaryResponse);
      setDocuments(documentsResponse.documents);
      setLoadState("ready");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "加载失败");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">W</span>
          <div>
            <strong>wishub</strong>
            <small>MVP · 严格问答</small>
          </div>
        </div>
        <button
          className={page === "knowledge" ? "nav-item active" : "nav-item"}
          onClick={() => setPage("knowledge")}
        >
          知识库
        </button>
        <button
          className={page === "qa" ? "nav-item active" : "nav-item"}
          onClick={() => setPage("qa")}
        >
          知识问答
        </button>
        <button
          className={page === "logs" ? "nav-item active" : "nav-item"}
          onClick={() => setPage("logs")}
        >
          调用日志
        </button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="breadcrumb">
              工作台 / {page === "knowledge" ? "知识库" : page === "qa" ? "知识问答" : "调用日志"}
            </p>
            <h1>{page === "knowledge" ? "知识库" : page === "qa" ? "知识问答" : "调用日志"}</h1>
          </div>
          <span className="mode-pill">严格知识库模式</span>
        </header>

        {loadState === "error" ? (
          <BoundaryCard
            tone="error"
            title="摘要加载失败"
            detail={loadError || "无法获取当前知识库状态，请重试。"}
            actionLabel="重试"
            onAction={reload}
          />
        ) : page === "knowledge" ? (
          <KnowledgeBasePage
            summary={summary}
            documents={documents}
            loading={loadState === "loading"}
            onReload={reload}
          />
        ) : page === "qa" ? (
          <QAPage summary={summary} onGoKnowledge={() => setPage("knowledge")} />
        ) : (
          <LLMLogsPage />
        )}
      </main>
    </div>
  );
}

function KnowledgeBasePage({
  summary,
  documents,
  loading,
  onReload,
}: {
  summary: KnowledgeBaseSummary;
  documents: KnowledgeDocument[];
  loading: boolean;
  onReload: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadMessage, setUploadMessage] = useState("");

  const readyText = useMemo(() => {
    if (summary.status === "PROCESSING") {
      return "有文档处理中";
    }
    if (summary.status === "READY") {
      return "知识库已准备就绪";
    }
    return "暂无可问答文档";
  }, [summary.status]);

  function onSelect(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    if (!selected) {
      setUploadState("idle");
      setUploadMessage("");
      return;
    }
    if (!selected.name.toLowerCase().endsWith(".md")) {
      setFile(null);
      setUploadState("error");
      setUploadMessage("仅支持 Markdown 文件（.md）");
      return;
    }
    setUploadState("selected");
    setUploadMessage(`${selected.name} · ${formatBytes(selected.size)} · 待上传`);
  }

  async function onUpload() {
    if (!file || uploadState === "uploading" || uploadState === "processing") {
      return;
    }
    if (!file.name.toLowerCase().endsWith(".md")) {
      setUploadState("error");
      setUploadMessage("仅支持 Markdown 文件（.md）");
      return;
    }

    try {
      setUploadState("uploading");
      setUploadMessage("正在上传文件…");
      const response = await uploadDocument(file);
      setUploadState("processing");
      setUploadMessage(response.message);
      const finalStatus = await pollDocument(response.documentId);
      if (finalStatus.status === "READY") {
        setUploadState("success");
        setUploadMessage(`${finalStatus.filename} 已加入知识库，可用于问答`);
        setFile(null);
        await onReload();
        return;
      }
      setUploadState("error");
      setUploadMessage(finalStatus.failureMessage || "处理失败，未加入知识库");
      await onReload();
    } catch (error) {
      setUploadState("error");
      setUploadMessage(readableError(error));
    }
  }

  return (
    <section className="page-grid">
      <div className="panel hero-panel">
        <div>
          <p className="eyebrow">单文件 · 仅支持 .md · 处理完成后可用于问答</p>
          <h2>管理当前可用于问答的 Markdown 文档</h2>
          <p>{summary.boundaryText}</p>
        </div>
        <div className="stat-card">
          <span>有效目录数</span>
          <strong>{loading ? "…" : summary.readyDocumentCount}</strong>
          <small>{readyText}</small>
        </div>
      </div>

      <div className="panel upload-panel">
        <div className="section-title">
          <div>
            <h3>上传 Markdown</h3>
            <p>上传成功后会进入解析和索引处理，完成后才参与问答。</p>
          </div>
          <button className="ghost-button" onClick={() => void onReload()}>
            刷新
          </button>
        </div>

        <label className={`dropzone ${uploadState}`}>
          <input type="file" accept=".md,text/markdown" onChange={onSelect} />
          <strong>{file ? file.name : "选择一个 Markdown 文件"}</strong>
          <span>{uploadMessage || "拖放或点击选择，MVP 暂不支持批量、替换和删除。"}</span>
        </label>

        <div className="upload-actions">
          <button
            className="primary-button"
            disabled={!file || uploadState === "uploading" || uploadState === "processing"}
            onClick={() => void onUpload()}
          >
            {uploadState === "uploading" || uploadState === "processing" ? "处理中" : "上传并入库"}
          </button>
          <span className={`state-text ${uploadState}`}>{stateLabel(uploadState)}</span>
        </div>
      </div>

      <div className="panel documents-panel">
        <div className="section-title">
          <div>
            <h3>有效文档目录</h3>
            <p>只展示处理成功且可问答的文档。</p>
          </div>
          <span>{documents.length} 条</span>
        </div>

        {documents.length === 0 ? (
          <BoundaryCard
            tone="empty"
            title="当前暂无知识库文档"
            detail="上传一个 Markdown 文件，处理完成后就能在这里看到目录，并用于严格基于知识库的问答。"
          />
        ) : (
          <div className="document-list">
            {documents.map((document) => (
              <article className="document-row" key={document.id}>
                <div>
                  <strong>{document.filename}</strong>
                  <span>
                    Markdown · {formatBytes(document.sizeBytes)} · {document.chunkCount} 个切片
                  </span>
                </div>
                <span className="ready-badge">可问答</span>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function QAPage({
  summary,
  onGoKnowledge,
}: {
  summary: KnowledgeBaseSummary;
  onGoKnowledge: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QAResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || submitting) {
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      setResult(await askQuestion(question.trim()));
    } catch (requestError) {
      setResult(null);
      setError(readableError(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="qa-layout">
      <div className="panel qa-composer-panel">
        <p className="eyebrow">仅基于知识库</p>
        <h2>用自然语言查询当前知识库</h2>
        <p>回答会附带引用依据。证据不足时，系统会拒答或要求补充问题信息。</p>

        <form className="question-form" onSubmit={(event) => void onSubmit(event)}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="输入一个关于知识库的问题…"
          />
          <button className="primary-button" disabled={submitting || !question.trim()}>
            {submitting ? "检索中" : "提交问题"}
          </button>
        </form>

        <div className="quick-questions">
          {["如何上传一个 Markdown 文档并让它参与问答？", "哪些文档可以参与问答？"].map(
            (item) => (
              <button key={item} onClick={() => setQuestion(item)}>
                {item}
              </button>
            ),
          )}
        </div>
      </div>

      <div className="panel answer-panel">
        <div className="section-title">
          <div>
            <h3>回答结果</h3>
            <p>当前有效文档数：{summary.readyDocumentCount}</p>
          </div>
        </div>

        {error ? (
          <BoundaryCard
            tone="error"
            title="本次问答未完成"
            detail={`${error}。未生成未经验证的回答。`}
          />
        ) : result ? (
          <QAResultView result={result} onGoKnowledge={onGoKnowledge} />
        ) : (
          <BoundaryCard
            tone="empty"
            title="等待提问"
            detail="输入一个具体问题后，系统会先检索知识库，再基于证据回答。"
          />
        )}
      </div>
    </section>
  );
}

function LLMLogsPage() {
  const [logs, setLogs] = useState<LLMCallLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchLLMLogs();
      setLogs(response.logs);
      setTotal(response.total);
    } catch (requestError) {
      setError(readableError(requestError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  return (
    <section className="logs-layout">
      <div className="panel logs-panel">
        <div className="section-title">
          <div>
            <p className="eyebrow">LLM Observability</p>
            <h2>大模型请求与响应日志</h2>
            <p>仅记录实际进入大模型生成链路的问答。目录查询、空库、澄清和检索前拒答不会产生大模型调用。</p>
          </div>
          <button className="ghost-button" onClick={() => void loadLogs()}>
            刷新日志
          </button>
        </div>

        {loading ? (
          <BoundaryCard tone="info" title="正在加载日志" detail="正在读取最近的大模型调用记录。" />
        ) : error ? (
          <BoundaryCard tone="error" title="日志加载失败" detail={error} actionLabel="重试" onAction={loadLogs} />
        ) : logs.length === 0 ? (
          <BoundaryCard
            tone="empty"
            title="暂无大模型调用日志"
            detail="完成一次需要大模型生成的知识问答后，这里会展示请求 messages 和响应内容。"
          />
        ) : (
          <div className="log-list">
            <p className="log-total">共 {total} 条，当前展示最近 {logs.length} 条</p>
            {logs.map((log) => (
              <article className="log-card" key={log.id}>
                <div className="log-card-header">
                  <div>
                    <strong>{log.question}</strong>
                    <span>
                      使用模型：{log.modelId || "unknown"} · {formatDateTime(log.createdAt)} · {log.latencyMs} ms
                    </span>
                  </div>
                  <span className={log.status === "SUCCESS" ? "ready-badge" : "error-badge"}>
                    {log.status === "SUCCESS" ? "成功" : "失败"}
                  </span>
                </div>

                {log.errorMessage ? (
                  <div className="log-error">错误：{log.errorMessage}</div>
                ) : null}

                <details open>
                  <summary>请求大模型</summary>
                  <JsonBlock value={log.request} />
                </details>
                <details open>
                  <summary>大模型原始响应</summary>
                  <JsonBlock value={log.responseText || ""} />
                </details>
                <details>
                  <summary>解析响应</summary>
                  <JsonBlock value={log.parsedResponse} />
                </details>
                <details>
                  <summary>最终返回给页面的数据</summary>
                  <JsonBlock value={log.finalResult} />
                </details>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  const content = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return <pre className="json-block">{content || "null"}</pre>;
}

function QAResultView({
  result,
  onGoKnowledge,
}: {
  result: QAResult;
  onGoKnowledge: () => void;
}) {
  if (result.type === "answer") {
    return (
      <article className="answer-card">
        <span className="ready-badge">基于知识库的回答</span>
        <p>{result.answer}</p>
        <div className="checks">
          <span>找到依据：{result.checks.foundEvidence ? "是" : "否"}</span>
          <span>外部知识：{result.checks.externalKnowledgeUsed ? "是" : "否"}</span>
          <span>引用文档：{result.checks.citationDocumentCount}</span>
        </div>
        <div className="citations">
          <h4>引用依据</h4>
          {result.citations.map((citation) => (
            <blockquote key={citation.chunkId}>
              <strong>{citation.documentName}</strong>
              {citation.headingPath ? <span>{citation.headingPath}</span> : null}
              <p>{citation.excerpt}</p>
            </blockquote>
          ))}
        </div>
      </article>
    );
  }

  if (result.type === "empty_knowledge_base") {
    return (
      <BoundaryCard
        tone="empty"
        title={result.message}
        detail={result.detail}
        actionLabel="去上传 Markdown"
        onAction={onGoKnowledge}
      />
    );
  }

  return (
    <BoundaryCard
      tone={result.type === "refusal" ? "warning" : "info"}
      title={result.message}
      detail={result.detail}
    />
  );
}

function BoundaryCard({
  tone,
  title,
  detail,
  actionLabel,
  onAction,
}: {
  tone: "empty" | "error" | "warning" | "info";
  title: string;
  detail: string;
  actionLabel?: string;
  onAction?: () => void | Promise<void>;
}) {
  return (
    <div className={`boundary-card ${tone}`}>
      <strong>{title}</strong>
      <p>{detail}</p>
      {actionLabel && onAction ? (
        <button className="ghost-button" onClick={() => void onAction()}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

async function pollDocument(documentId: string) {
  for (let index = 0; index < 60; index += 1) {
    const status = await fetchDocumentStatus(documentId);
    if (status.status === "READY" || status.status === "FAILED") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return fetchDocumentStatus(documentId);
}

function readableError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "请求失败，请稍后重试";
}

function stateLabel(state: UploadState) {
  switch (state) {
    case "selected":
      return "已选择";
    case "uploading":
      return "上传中";
    case "processing":
      return "处理中";
    case "success":
      return "成功";
    case "error":
      return "失败";
    default:
      return "等待选择";
  }
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default App;
