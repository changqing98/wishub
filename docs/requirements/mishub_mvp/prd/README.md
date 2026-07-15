# wishub（智慧中枢）MVP 产品文档索引

本目录用于统一存放 **wishub（智慧中枢）** 项目的 **mvp 版本** 产品文档。

当前迭代版本目录统一维护在：`docs/requirements/mishub_mvp/`

## 文档清单

- [01-prd-v1.1.md](./01-prd-v1.1.md) — 产品需求文档确认稿，定义目标用户、范围、规则、验收口径。
- [02-page-prototype-spec.md](./02-page-prototype-spec.md) — Web 首版页面原型说明，覆盖问答页、知识库管理页、证据预览页及关键交互流程。
- [03-states-and-copy.md](./03-states-and-copy.md) — 状态清单与提示文案，供设计、研发、测试统一对齐。
- [04-feature-breakdown.md](./04-feature-breakdown.md) — 功能拆解稿，面向研发、设计、测试进行模块拆分与交付边界定义。
- [05-test-acceptance-checklist.md](./05-test-acceptance-checklist.md) — 测试验收清单，面向产品、研发、测试统一验收场景、用例与通过标准。

## 当前版本结论

- 项目名称：wishub（智慧中枢）
- 当前迭代：mvp
- 产品形态：Web 页面
- 目标用户：外部客户
- 核心策略：严格知识库问答，**有证据才回答，无依据直接拒答或引导补充**
- 证据展示：文档名 + 引用片段 + 在线预览跳转（支持页码定位）
- 信息开放边界：客户只能看引用片段，不能查看完整原文

## 目录维护约定

- 本次 mvp 迭代涉及的产品、设计、需求相关文件，统一维护在 `mishub_mvp` 目录下。
- 后续若继续补充 PRD、原型说明、功能拆解、测试验收等文件，均默认放在当前目录体系下。

## 使用建议

- 设计产出建议优先依据 `02-page-prototype-spec.md`
- 研发拆分建议优先依据 `01-prd-v1.1.md`、`03-states-and-copy.md` 与 `04-feature-breakdown.md`
- 测试验收建议重点关注：**不乱答、不错引、不过度暴露原文、模糊问题能友好澄清**
