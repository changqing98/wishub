# wishub（智慧中枢）MVP 接口与数据契约草案

本文档用于在产品需求、页面原型与测试验收之间，建立一份可供前后端协作的接口与数据契约草案。本文档不是最终技术实现说明，而是 **MVP 版本的协作基线**。

---

## 1. 文档目标

本草案主要用于：

1. 统一前后端资源对象命名
2. 统一页面状态与接口状态的映射关系
3. 明确问答、证据、预览、知识库管理的接口边界
4. 为研发排期、联调、自测提供统一输入

---

## 2. 适用范围

- 项目名称：wishub（智慧中枢）
- 当前迭代版本：mvp
- 当前文档目录：`docs/requirements/mishub_mvp/prd/`

本草案覆盖：
- 客户问答页接口
- 最近提问记录接口
- 证据预览接口
- 知识库上传与目录管理接口
- 文件删除与替换接口

本草案不覆盖：
- 权限与鉴权体系
- 多租户隔离
- 运维监控接口
- 内部模型调用细节
- 异步任务调度实现细节

---

## 3. 契约设计原则

### 3.1 结果类型必须清晰区分
问答接口不能只返回一个 `answer` 字段，而应明确区分：
- 成功回答
- 需要澄清
- 无依据拒答
- 系统异常

### 3.2 证据与答案必须强绑定
只要返回有效答案，就必须返回证据列表；若无证据，不应返回确定性答案。

### 3.3 预览接口必须天然受控
预览接口返回的内容只能满足“核验证据”，不能满足“阅读全文”。

### 3.4 文件状态与问答生效状态必须一致
只有 `READY` 状态文件可以参与问答；`PROCESSING`、`FAILED`、`DELETED` 文件不得被检索命中。

---

## 4. 核心资源对象

## 4.1 KnowledgeNode
用于描述目录树节点。

### 字段
| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 节点唯一标识 |
| name | string | 节点名称 |
| nodeType | enum | `DIRECTORY` / `FILE` |
| parentId | string \| null | 父节点 ID |
| path | string | 完整路径 |
| children | array | 子节点列表，仅目录节点使用 |
| fileId | string \| null | 关联文件 ID，目录节点为空 |
| status | enum \| null | 仅文件节点使用 |

---

## 4.2 KnowledgeFile
用于描述知识文件对象。

### 字段
| 字段 | 类型 | 说明 |
|---|---|---|
| fileId | string | 文件唯一标识 |
| fileName | string | 文件名 |
| fileType | enum | `MARKDOWN` / `TXT` / `PDF` / `WORD` |
| path | string | 文件完整路径 |
| directoryId | string \| null | 所属目录 ID |
| status | enum | `UPLOADING` / `PROCESSING` / `READY` / `FAILED` / `DELETED` |
| sourceType | enum | `SINGLE_FILE` / `FOLDER_IMPORT` / `REPLACE` |
| updatedAt | string | 更新时间 |
| errorMessage | string \| null | 失败说明 |

---

## 4.3 UploadJob
用于描述上传或文件夹导入任务。

### 字段
| 字段 | 类型 | 说明 |
|---|---|---|
| jobId | string | 任务 ID |
| jobType | enum | `FILE_UPLOAD` / `FOLDER_UPLOAD` / `FILE_REPLACE` |
| status | enum | `PENDING` / `RUNNING` / `PARTIAL_SUCCESS` / `SUCCESS` / `FAILED` |
| totalCount | number | 文件总数 |
| successCount | number | 成功数量 |
| failedCount | number | 失败数量 |
| startedAt | string | 开始时间 |
| finishedAt | string \| null | 完成时间 |
| affectedFileIds | string[] | 受影响文件列表 |

---

## 4.4 QuestionRecord
用于描述一次用户提问与回答结果。

### 字段
| 字段 | 类型 | 说明 |
|---|---|---|
| questionId | string | 问题 ID |
| userId | string | 当前用户标识 |
| questionText | string | 用户提问内容 |
| answerStatus | enum | `ANSWERED` / `NEED_CLARIFICATION` / `NO_ANSWER` / `ERROR` |
| answerText | string \| null | 直接答案 |
| answerSummary | string \| null | 一句话说明 |
| clarificationPrompts | string[] | 澄清问题列表 |
| evidences | EvidenceItem[] | 证据列表 |
| createdAt | string | 提问时间 |

---

## 4.5 EvidenceItem
用于描述一条证据。

### 字段
| 字段 | 类型 | 说明 |
|---|---|---|
| evidenceId | string | 证据 ID |
| fileId | string | 关联文件 ID |
| fileName | string | 文档名 |
| filePath | string | 文档路径 |
| fileType | enum | 文件类型 |
| snippet | string | 命中片段 |
| pageNumber | number \| null | 页码，PDF/Word 优先返回 |
| anchorText | string \| null | 锚点文本，Markdown/TXT 可使用 |
| previewAvailable | boolean | 是否可预览 |
| rank | number | 当前回答中的排序 |

---

## 4.6 PreviewPayload
用于描述证据预览内容。

### 字段
| 字段 | 类型 | 说明 |
|---|---|---|
| evidenceId | string | 证据 ID |
| fileId | string | 文件 ID |
| fileName | string | 文件名 |
| filePath | string | 文件路径 |
| fileType | enum | 文件类型 |
| pageNumber | number \| null | 当前页码 |
| snippetBlocks | array | 片段块列表 |
| previewMode | enum | 固定为 `SNIPPET_ONLY` |
| notice | string | “仅展示相关引用内容”提示 |

### snippetBlocks 子项建议
| 字段 | 类型 | 说明 |
|---|---|---|
| blockId | string | 片段块 ID |
| text | string | 片段内容 |
| highlighted | boolean | 是否高亮 |
| blockOrder | number | 顺序 |

---

## 5. 状态枚举建议

## 5.1 文件状态
| 枚举值 | 说明 |
|---|---|
| UPLOADING | 正在上传 |
| PROCESSING | 已上传，正在处理 |
| READY | 已生效，可参与问答 |
| FAILED | 处理失败 |
| DELETED | 已删除，不可再用 |

## 5.2 问答结果状态
| 枚举值 | 说明 |
|---|---|
| ANSWERED | 有证据支撑，正常回答 |
| NEED_CLARIFICATION | 问题不清晰，需要补充 |
| NO_ANSWER | 无依据，明确拒答 |
| ERROR | 系统异常 |

## 5.3 上传任务状态
| 枚举值 | 说明 |
|---|---|
| PENDING | 已创建，待执行 |
| RUNNING | 正在执行 |
| PARTIAL_SUCCESS | 部分成功 |
| SUCCESS | 全部成功 |
| FAILED | 全部失败或整体失败 |

---

## 6. 接口清单总览

| 模块 | 方法 | 路径 | 用途 |
|---|---|---|---|
| 问答 | POST | `/api/mvp/chat/questions` | 提交问题并获取结果 |
| 问答 | GET | `/api/mvp/chat/questions/{questionId}` | 查询问题详情 |
| 历史 | GET | `/api/mvp/chat/recent-questions` | 获取最近提问记录 |
| 预览 | GET | `/api/mvp/evidences/{evidenceId}/preview` | 获取证据预览 |
| 上传 | POST | `/api/mvp/knowledge/upload/file` | 上传单文件 |
| 上传 | POST | `/api/mvp/knowledge/upload/folder` | 上传文件夹 |
| 任务 | GET | `/api/mvp/knowledge/jobs/{jobId}` | 查询上传任务状态 |
| 管理 | GET | `/api/mvp/knowledge/tree` | 获取目录树 |
| 管理 | GET | `/api/mvp/knowledge/files` | 获取文件列表 |
| 管理 | GET | `/api/mvp/knowledge/files/{fileId}` | 获取文件详情 |
| 管理 | POST | `/api/mvp/knowledge/files/{fileId}/replace` | 替换文件 |
| 管理 | DELETE | `/api/mvp/knowledge/files/{fileId}` | 删除文件 |

---

## 7. 问答接口契约

## 7.1 提交问题
### 接口
`POST /api/mvp/chat/questions`

### 请求体示例
```json
{
  "questionText": "如何配置回调地址？",
  "clientRequestId": "web-1720000001",
  "context": {
    "source": "customer-web"
  }
}
```

### 响应体示例：正常回答
```json
{
  "questionId": "q_001",
  "answerStatus": "ANSWERED",
  "answerText": "你可以在开发者设置页面配置回调地址，并完成验证后启用。",
  "answerSummary": "回调地址需要使用可访问的 HTTPS 地址。",
  "clarificationPrompts": [],
  "evidences": [
    {
      "evidenceId": "ev_001",
      "fileId": "file_101",
      "fileName": "开发者接入指南.pdf",
      "filePath": "/docs/openapi/开发者接入指南.pdf",
      "fileType": "PDF",
      "snippet": "回调地址必须为 HTTPS，并且可以被平台访问。",
      "pageNumber": 12,
      "anchorText": null,
      "previewAvailable": true,
      "rank": 1
    }
  ],
  "createdAt": "2026-07-16T10:00:00Z"
}
```

### 响应体示例：需要澄清
```json
{
  "questionId": "q_002",
  "answerStatus": "NEED_CLARIFICATION",
  "answerText": null,
  "answerSummary": null,
  "clarificationPrompts": [
    "请补充一下具体产品、功能或页面名称。",
    "如果你遇到了报错，也可以补充错误码或报错信息。"
  ],
  "evidences": [],
  "createdAt": "2026-07-16T10:01:00Z"
}
```

### 响应体示例：无依据拒答
```json
{
  "questionId": "q_003",
  "answerStatus": "NO_ANSWER",
  "answerText": "当前知识库中没有足够信息回答这个问题。",
  "answerSummary": null,
  "clarificationPrompts": [],
  "evidences": [],
  "createdAt": "2026-07-16T10:02:00Z"
}
```

### 响应体示例：异常
```json
{
  "questionId": "q_004",
  "answerStatus": "ERROR",
  "answerText": null,
  "answerSummary": null,
  "clarificationPrompts": [],
  "evidences": [],
  "errorCode": "CHAT_SERVICE_UNAVAILABLE",
  "errorMessage": "当前暂时无法完成回答，请稍后重试。",
  "createdAt": "2026-07-16T10:03:00Z"
}
```

### 合同约束
- `ANSWERED` 时，`answerText` 必填，`evidences.length >= 1`
- `NEED_CLARIFICATION` 时，`clarificationPrompts.length >= 1`
- `NO_ANSWER` 时，不应返回证据列表冒充有效答案
- `ERROR` 时，前端应展示系统异常状态，而非业务拒答状态

---

## 7.2 查询问题详情
### 接口
`GET /api/mvp/chat/questions/{questionId}`

### 用途
- 用于最近提问回看
- 用于页面刷新后恢复单条问答结果

### 响应建议
与 `POST /chat/questions` 结果结构保持一致。

---

## 7.3 获取最近提问记录
### 接口
`GET /api/mvp/chat/recent-questions?limit=10`

### 响应示例
```json
{
  "items": [
    {
      "questionId": "q_001",
      "questionText": "如何配置回调地址？",
      "answerStatus": "ANSWERED",
      "createdAt": "2026-07-16T10:00:00Z"
    },
    {
      "questionId": "q_002",
      "questionText": "企业版呢？",
      "answerStatus": "NEED_CLARIFICATION",
      "createdAt": "2026-07-16T10:01:00Z"
    }
  ]
}
```

### 合同约束
- 仅返回当前用户最近记录
- `limit` 默认 10，MVP 可限制最大 20

---

## 8. 证据预览接口契约

## 8.1 获取证据预览
### 接口
`GET /api/mvp/evidences/{evidenceId}/preview`

### 响应示例
```json
{
  "evidenceId": "ev_001",
  "fileId": "file_101",
  "fileName": "开发者接入指南.pdf",
  "filePath": "/docs/openapi/开发者接入指南.pdf",
  "fileType": "PDF",
  "pageNumber": 12,
  "previewMode": "SNIPPET_ONLY",
  "notice": "当前仅展示与该回答相关的引用内容，不提供完整原文浏览。",
  "snippetBlocks": [
    {
      "blockId": "blk_1",
      "text": "回调地址必须为 HTTPS，并且可以被平台访问。",
      "highlighted": true,
      "blockOrder": 1
    },
    {
      "blockId": "blk_2",
      "text": "完成配置后，需要在控制台进行回调验证。",
      "highlighted": false,
      "blockOrder": 2
    }
  ]
}
```

### 合同约束
- 不返回完整文档正文
- 不返回可拼接成全文的长列表内容
- `previewMode` 在 mvp 中固定为 `SNIPPET_ONLY`
- 如果不可预览，应返回明确错误码

### 不可预览示例
```json
{
  "errorCode": "PREVIEW_NOT_AVAILABLE",
  "errorMessage": "当前暂时无法打开引用内容，请稍后重试。"
}
```

---

## 9. 知识库上传与管理接口契约

## 9.1 上传单文件
### 接口
`POST /api/mvp/knowledge/upload/file`

### 请求
`multipart/form-data`

### 字段建议
| 字段 | 类型 | 说明 |
|---|---|---|
| file | binary | 上传文件 |
| targetPath | string | 目标路径，可为空 |

### 响应示例
```json
{
  "jobId": "job_001",
  "jobType": "FILE_UPLOAD",
  "status": "PENDING",
  "totalCount": 1,
  "successCount": 0,
  "failedCount": 0
}
```

---

## 9.2 上传文件夹
### 接口
`POST /api/mvp/knowledge/upload/folder`

### 请求说明
建议使用前端打包目录结构后上传，服务端按路径恢复层级。

### 请求体建议
```json
{
  "folderName": "openapi-docs",
  "files": [
    {
      "relativePath": "guide/开发者接入指南.pdf",
      "fileName": "开发者接入指南.pdf",
      "fileType": "PDF"
    },
    {
      "relativePath": "faq/常见问题.txt",
      "fileName": "常见问题.txt",
      "fileType": "TXT"
    }
  ]
}
```

### 响应示例
```json
{
  "jobId": "job_002",
  "jobType": "FOLDER_UPLOAD",
  "status": "PENDING",
  "totalCount": 2,
  "successCount": 0,
  "failedCount": 0
}
```

### 合同约束
- 服务端必须保留 `relativePath`
- 路径恢复后应可在目录树中呈现

---

## 9.3 查询上传任务状态
### 接口
`GET /api/mvp/knowledge/jobs/{jobId}`

### 响应示例
```json
{
  "jobId": "job_002",
  "jobType": "FOLDER_UPLOAD",
  "status": "PARTIAL_SUCCESS",
  "totalCount": 2,
  "successCount": 1,
  "failedCount": 1,
  "affectedFileIds": ["file_101"],
  "startedAt": "2026-07-16T10:00:00Z",
  "finishedAt": "2026-07-16T10:03:00Z"
}
```

---

## 9.4 获取目录树
### 接口
`GET /api/mvp/knowledge/tree`

### 响应示例
```json
{
  "root": {
    "id": "dir_root",
    "name": "root",
    "nodeType": "DIRECTORY",
    "parentId": null,
    "path": "/",
    "children": [
      {
        "id": "dir_docs",
        "name": "docs",
        "nodeType": "DIRECTORY",
        "parentId": "dir_root",
        "path": "/docs",
        "children": []
      }
    ]
  }
}
```

### 合同约束
- 目录树中仅 `READY`、`PROCESSING`、`FAILED` 文件需要展示
- `DELETED` 文件不应继续出现在目录树中

---

## 9.5 获取文件列表
### 接口
`GET /api/mvp/knowledge/files?directoryId=dir_docs&status=READY`

### 用途
- 右侧文件列表
- 条件筛选展示

### 响应示例
```json
{
  "items": [
    {
      "fileId": "file_101",
      "fileName": "开发者接入指南.pdf",
      "fileType": "PDF",
      "path": "/docs/openapi/开发者接入指南.pdf",
      "status": "READY",
      "updatedAt": "2026-07-16T10:04:00Z",
      "errorMessage": null
    }
  ]
}
```

---

## 9.6 获取文件详情
### 接口
`GET /api/mvp/knowledge/files/{fileId}`

### 用途
- 查看单文件基础信息
- 支撑管理页右侧详情区

---

## 9.7 替换文件
### 接口
`POST /api/mvp/knowledge/files/{fileId}/replace`

### 请求
`multipart/form-data`

### 合同约束
- 替换后保留原路径
- 替换期间旧内容不应与新状态混淆
- 替换完成后问答应以新内容为准

### 响应示例
```json
{
  "jobId": "job_003",
  "jobType": "FILE_REPLACE",
  "status": "PENDING",
  "totalCount": 1,
  "successCount": 0,
  "failedCount": 0
}
```

---

## 9.8 删除文件
### 接口
`DELETE /api/mvp/knowledge/files/{fileId}`

### 响应示例
```json
{
  "fileId": "file_101",
  "status": "DELETED",
  "message": "文件已从知识库中移除。"
}
```

### 合同约束
- 删除成功后，该文件不得继续参与问答
- 前端应同步更新列表与目录树状态

---

## 10. 错误码建议

| 错误码 | 场景 | 前端处理建议 |
|---|---|---|
| VALIDATION_ERROR | 参数错误 | 展示表单级提示 |
| QUESTION_TOO_SHORT | 问题过短 | 可转为澄清提示 |
| UNSUPPORTED_FILE_TYPE | 文件类型不支持 | 展示支持范围 |
| FILE_PROCESSING_FAILED | 文件处理失败 | 展示失败状态与重试建议 |
| FILE_NOT_FOUND | 文件不存在 | 刷新列表并提示 |
| PREVIEW_NOT_AVAILABLE | 预览不可用 | 展示预览失败提示 |
| CHAT_SERVICE_UNAVAILABLE | 问答服务异常 | 展示系统异常状态 |
| TREE_LOAD_FAILED | 目录树加载失败 | 展示加载失败状态 |

---

## 11. 前后端联调注意事项

### 11.1 前端状态映射建议
| 接口状态 | 页面表现 |
|---|---|
| ANSWERED | 回答成功 + 证据卡片 |
| NEED_CLARIFICATION | 补充问题提示 |
| NO_ANSWER | 不知道型回答 |
| ERROR | 异常提示 |
| READY | 文件可用 |
| PROCESSING | 文件处理中 |
| FAILED | 文件失败 |
| DELETED | 文件从列表移除或标记不可用 |

### 11.2 联调重点
- `ANSWERED` 是否必带证据
- `NO_ANSWER` 是否被错误展示成异常
- `NEED_CLARIFICATION` 是否支持前端二次提问链路
- 预览接口是否存在全文暴露风险
- 删除/替换后问答结果是否同步更新

---

## 12. 本草案的评审重点

在 Review 时，建议重点看以下问题：

1. 资源对象是否覆盖了 MVP 所需页面
2. 字段命名是否足够稳定，便于后续扩展
3. 问答结果状态是否能支撑“回答 / 澄清 / 拒答 / 异常”四类分流
4. 预览接口是否真正满足“可核验但不暴露全文”
5. 上传、替换、删除与问答生效状态之间是否存在歧义

---

## 13. 后续建议

若本稿 Review 通过，下一步建议补齐：
- 前端页面状态流转图
- 知识文件处理状态机
- 问答结果埋点与分析字段
- 开发任务拆解与接口 Mock 数据
