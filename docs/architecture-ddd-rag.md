# 通用知识库与智能客服大模型应用架构设计（Python + DDD）

- **项目**：wishub
- **版本**：v0.1
- **日期**：2026-07-12
- **目标**：构建一个可扩展、可追溯、可观测的通用知识库与智能客服系统，支持多租户/多业务线演进。

---

## 1. 背景与目标

### 1.1 背景

系统面向“知识管理 + 智能问答客服”场景，需兼顾：

1. 多来源知识接入（文档、FAQ、网页、结构化数据）
2. 高质量问答（检索增强生成 RAG + 引用可追溯）
3. 业务可运营（反馈闭环、质量评估、A/B 实验）
4. 工程可演进（分层清晰、可替换模型/向量库）

### 1.2 架构目标

- **领域中心**：业务规则沉淀在 Domain，不被框架/SDK 绑死。
- **模型可替换**：LLM 供应商与业务逻辑解耦。
- **知识可版本化**：回答可追溯到文档版本与切片。
- **检索可配置**：支持不同场景下策略切换（Hybrid/Rerank/阈值）。
- **全链路可观测**：延迟、命中率、成本、幻觉风险可度量。
- **默认可降级**：模型超时、检索失败时可平滑兜底或转人工。

---

## 2. DDD 战略设计（Bounded Context）

建议拆分 6 个限界上下文：

1. **Knowledge Context（知识管理）**
   - 知识库、文档、版本、标签、发布流程
2. **Ingestion Context（数据处理）**
   - 解析、清洗、切片、Embedding、索引构建
3. **Retrieval Context（检索）**
   - Query 处理、向量召回、关键词召回、重排
4. **Conversation Context（会话客服）**
   - 会话状态、多轮上下文、回复生成、转人工
5. **LLM Gateway Context（模型网关）**
   - 多模型适配、Prompt 策略、工具调用、限流与成本治理
6. **Ops & Evaluation Context（运营评测）**
   - 反馈采集、离线评测、在线指标、告警审计

上下文之间通过 Application 层编排与事件通信，不直接跨层依赖基础设施实现。

---

## 3. 分层架构（战术设计）

采用四层架构：

1. **Interfaces 层（接口层）**
   - FastAPI Router / Controller
   - 请求参数校验、鉴权、响应 DTO

2. **Application 层（应用层）**
   - UseCase/Command/Query Handler
   - 事务边界、流程编排、权限控制

3. **Domain 层（领域层）**
   - Entity、Aggregate、Value Object
   - Domain Service、Domain Event、Repository 抽象

4. **Infrastructure 层（基础设施层）**
   - Repository 实现（PostgreSQL/pgvector）
   - LLM Provider 适配、向量检索引擎、MQ、对象存储

**依赖方向**：Interfaces -> Application -> Domain <- Infrastructure（依赖倒置）。

---

## 4. 核心领域模型建议

### 4.1 聚合（Aggregates）

- `KnowledgeBase`
  - 属性：id, name, tenant_id, visibility, retrieval_policy
  - 规则：策略变更需版本化并记录审计

- `Document`
  - 属性：id, kb_id, source_type, status, version, checksum
  - 规则：仅“已发布版本”可参与在线检索

- `ConversationSession`
  - 属性：id, user_id, channel, context_window, status
  - 规则：会话上下文遵循窗口/摘要策略

- `SupportTicket`（可选）
  - 属性：id, session_id, reason, priority, assignee
  - 规则：低置信度或高风险问答需自动转人工

### 4.2 值对象（Value Objects）

- `TenantId`, `UserId`, `DocVersion`, `ChunkId`
- `ConfidenceScore`, `Citation`, `TokenUsage`, `Cost`

### 4.3 领域服务（Domain Services）

- `RetrievalPolicyService`
- `AnswerQualityService`
- `EscalationDecisionService`
- `PromptPolicyService`

---

## 5. 关键业务流程

### 5.1 知识入库流程（异步）

`上传文档 -> 解析 -> 清洗 -> 切片 -> Embedding -> 索引 -> 发布`

- 每阶段产生任务状态：`PENDING/RUNNING/SUCCEEDED/FAILED`
- 失败支持重试与幂等（基于 checksum + version）
- 发布前进行质量门禁（文本有效率、切片覆盖率等）

### 5.2 问答流程（同步）

`用户提问 -> query 重写 -> 召回 -> 重排 -> 生成 -> 引用校验 -> 置信度判定 -> 返回/转人工`

输出建议包含：

- `answer`
- `citations[]`（文档ID、版本、段落定位）
- `confidence`
- `escalation`（是否建议转人工）

---

## 6. 技术选型建议（Python）

- **Web/API**：FastAPI
- **ORM**：SQLAlchemy 2.x
- **迁移**：Alembic
- **关系型数据库**：PostgreSQL
- **向量检索**：pgvector（MVP）
- **缓存**：Redis
- **异步任务**：Celery / RQ / Arq（三选一）
- **对象存储**：S3/MinIO
- **可观测**：OpenTelemetry + Prometheus + Grafana
- **日志与链路追踪**：结构化日志 + TraceId 全链路透传

---

## 7. 建议目录结构（映射当前 backend）

```text
backend/
  interfaces/
    api/
      v1/
        chat_controller.py
        kb_controller.py
    schemas/
  application/
    commands/
    queries/
    services/
    dto/
  domain/
    conversation/
      entities/
      value_objects/
      repositories/
      services/
      events/
    knowledge/
    retrieval/
    llm_gateway/
  infrastructure/
    persistence/
      models/
      repositories/
    vectorstore/
    llm/
      providers/
      prompt_templates/
    queue/
    storage/
  shared/
    kernel/
    config/
    logging/
```

---

## 8. 接口与契约建议

### 8.1 API（示例）

- `POST /api/v1/kb` 创建知识库
- `POST /api/v1/kb/{kb_id}/documents` 上传文档
- `POST /api/v1/kb/{kb_id}/publish` 发布版本
- `POST /api/v1/chat/ask` 问答
- `POST /api/v1/chat/{session_id}/feedback` 反馈

### 8.2 应用层契约（示例）

- `IngestDocumentCommand`
- `PublishKnowledgeBaseCommand`
- `AskQuestionQuery`
- `EscalateSessionCommand`

---

## 9. 非功能设计

### 9.1 安全与合规

- 多租户数据隔离（tenant_id 全链路约束）
- 传输与存储加密
- 敏感信息脱敏（日志/Prompt/输出）
- 审计日志（谁在何时改了什么）

### 9.2 性能与弹性

- 热门 query 缓存（语义缓存 + 答案缓存）
- 检索与生成超时控制
- 队列堆积告警与自动扩缩容

### 9.3 成本治理

- token 预算策略（按租户/应用）
- 模型分级路由（简单问题走轻量模型）
- 失败重试上限与熔断

---

## 10. 观测与评测体系

### 10.1 在线指标

- 请求量、P95/P99 延迟
- 检索命中率、无结果率
- 人工转接率
- 单请求 token 与成本
- 用户反馈好评率

### 10.2 离线评测

- 构建标准问答集（带标准引用）
- 评估维度：正确性、相关性、完整性、可追溯性
- 每次策略变更触发回归评测

---

## 11. 演进路线图

### Phase 1（MVP，2~4 周）

- 单租户
- 文档上传/解析/切片/索引
- 基础 RAG 问答 API
- 引用回传与基础日志

### Phase 2（可用化，4~8 周）

- 混合检索 + 重排
- 反馈闭环
- 低置信度转人工
- 观测面板

### Phase 3（规模化，8~12 周）

- 多租户与权限体系
- A/B 评测
- 成本治理与模型路由
- 完整审计与策略中心

---

## 12. 当前仓库落地建议（下一步）

结合当前代码基础（`backend/domain/domainsvc/llm_service.py` 已存在），建议优先落地：

1. 在 `domain` 中定义 `ConversationSession`、`Document` 聚合与仓储抽象
2. 在 `application` 新增 `AskQuestionUseCase` 与 `IngestDocumentUseCase`
3. 在 `infrastructure/llm` 新增 provider adapter（先一个实现）
4. 在 `interfaces/api/v1` 提供 `chat` 与 `kb` 最小 API
5. 用 Alembic 初始化数据库 schema（文档、切片、会话、消息、任务表）

---

## 13. 结语

该方案以 DDD 为核心，将“知识、检索、对话、模型网关、运营评测”解耦，保证了：

- MVP 快速上线
- 中期质量可优化
- 后期多租户与多模型可持续演进

可在不推翻现有结构的前提下，逐步从“可用”走向“可运营、可治理、可规模化”。
