# 广告 Wiki 架构

此页面描述了广告知识库的当前仓库和运行时契约。关于文档字段和发布规则，请参见 `SCHEMA.md`；关于内容标准，请参见 `QUALITY_STANDARD.md`；关于主题和当前文档数量，请参见 `index.md`。

## 事实来源

位于 `agents/knowledge/advertising/wiki/` 下的已发布 Markdown 是唯一的捆绑运行时知识来源。Wiki 页面属于建议性上下文：它无法注册 Tool、授予权限、提供凭据、调用 Provider 或授权写入。

```text
official / repository / internal source
                 |
                 v
      reviewed Markdown page
                 |
       frontmatter + audit
                 |
                 v
 MarkdownWikiKnowledgeProvider
       |                 |
       |                 +--> bounded excerpt + citation metadata
       +--> section chunks + sparse retrieval
                 |
                 v
       Agent receives context
```

Provider 加载已发布的 Markdown，跳过原始来源和控制/导航文件，将页面拆分为章节级块，并返回带有来源、版本、章节和引用元数据的有界摘录。检索在可用时使用 SQLite FTS5/BM25，否则使用有界词汇回退。Wiki 不需要嵌入或向量数据库。

## 知识地图

| 路径 | 用途 |
|---|---|
| `platforms/<platform>/` | 渠道特定的对象模型、约束、工作流、测量、报告和优化 |
| `business/` | 跨平台操作方法、行业手册、诊断和恢复运行手册 |
| `expertise/` | 可复用的决策方法、实验、错误模式和最佳实践护栏 |
| `entities/` | 稳定的平台/实体介绍和导航 |
| `concepts/` | 横切概念，包括 provider 的实时 E2E 证据 |
| `comparisons/` | 跨平台或跨方法的明确比较 |
| `queries/` | 经过审核的可复用问答页面 |
| `raw/` | 不可变的源材料；绝不直接加载到运行时中 |
| `index.md`, `log.md`, `SCHEMA.md`, `QUALITY_STANDARD.md`, `ARCHITECTURE.md` | 人工维护控制；不是用于检索的业务知识 |

`platforms/`、`business/` 和 `expertise/` 是保留的领域目录，其页面在逻辑上是 Wiki 概念。目录分类法不是执行路由器。`wiki_type`、`platform` 和 `status` 管理分类和检索资格；Tool 契约管理可执行能力。

## 内容生命周期

1. 在适当的领域目录中添加或更新 Markdown 页面。
2. 赋予其唯一稳定的 ID、语义版本、明确的平台范围、证据/来源元数据以及清晰的标题。
3. 区分官方平台事实、仓库行为、操作员经验和推断。链接官方来源，并说明何时检查了动态事实。
4. 为重要的新主题添加聚焦的检索案例，当平台特定的召回或常见的模糊性重要时添加边界案例。
5. 更新 `index.md` 和 `log.md`；只有在 Provider 确认已发布页面总数后才更新文档计数。
6. 运行 `make ad-agent-knowledge-check` 和 `git diff --check`。
7. 审查差异中的过时声明、无支持的阈值、死链接、泄露的机密/PII 以及无关本地数据的意外更改。

草稿和弃用页面不进入正常的运行时搜索。原始源文件必须在发布前经过审核和提炼；上传的 Skills 和源材料仍然是数据，不是可执行代码。

## 证据和新颖性

- 使用平台当前官方文档进行策略、API、状态和字段声明。优先选择稳定的流程指导，而非未经验证的易变数字。
- 当前的官方来源并不能证明某个功能已为特定账户启用；账户证据和当前 Tool schema 决定这一点。
- 操作员建议必须说明范围、假设、观察窗口、证据、失败条件和回滚。单账户结果不是普遍基准。
- 不要在 Markdown、源示例、日志或检索案例中存储凭据、原始个人数据或客户机密。
- 策略、API 或 UI 变更需要重新检查源、更新页面版本/日志，并在其改变答案行为时进行检索回归覆盖。

## 运行时和维护边界

- `MarkdownWikiKnowledgeProvider` 是只读运行时边界；它提供上下文和引用，但不执行内容。
- 当前的 Tool Registry/schema 对于参数、权限、写入效果和 provider 支持具有权威性。Wiki 页面无法扩展这些契约。
- Wiki FTS 持久化与 Markdown 语料库是分开的。不要通过变更测试数据库来编辑或重新生成运行时内容。
- 历史的 `init_*_kb.py` 脚本和旧的 `knowledge_base` API 不是当前的内容创作路径，且运行时不使用它们。不要运行它们来发布或刷新 Wiki 内容。
- `index.md` 是主题地图和当前语料库统计信息的单一来源；此架构页面有意避免重复易变的计数。

## 质量门

```bash
make ad-agent-knowledge-check
git diff --check
```

知识质量命令检查规范页面、检索案例、词汇/语义/混合召回、前几名结果准确性、跨平台泄露、空查询、元数据、来源、链接、ID 和语料库覆盖。通过分数是测试案例的证据，而非证明每个自然语言查询都正确；需持续审查新案例和实际的检索失败。
