# 上下文、检索与模型执行收尾

上一轮成果已作为 `d68e420` 推送到 `main`。本轮仍使用单 Harness Runtime，
没有增加广告专用生命周期、Provider 执行入口或数据库。

## 实际修复

| 问题 | 归属与实现 | 回归依据 |
| --- | --- | --- |
| 检索内容在专家指导与知识记录中重复出现 | Harness 动态上下文只把知识保留在结构化记录中 | `test_prompt_context_assembly.py` |
| 原始知识元数据挤掉有效片段、JSON 被半截裁剪 | Platform `data/knowledge_context.py` 白名单投影、有限摘要、完整 JSON 记录裁剪 | `test_knowledge_context.py` |
| 总预算漏掉列表形式的知识 | 应用 context service 按实际序列化字符计费，Skill 上下文计入分隔符 | `test_context_delivery_evidence.py` |
| 空匹配也注入前几个 Skill | Catalog 只选择匹配、显式来源或 `always_on` binding；支持中文主题片段 | `test_skill_reference_selection.py` |
| 蓝图过滤仍读取旧 `platforms` 字段 | 应用使用当前 `namespaces` 列表，缓存仍按规范化 scope 复用 | `test_context_delivery_evidence.py` |
| 模糊请求的资料检索 Tool 不可见 | 从注册 Tool 的 `semantic_discovery` 元数据保留发现入口；不更改明确 Tool/渠道/别名选择或拒绝路径 | `test_discovery_availability.py` |
| 网页 Tool 可见就强制执行 | 不能仅因一般疑问句命中读请求就强制搜索；保留显式检索和注册实时查询别名 | `test_tool_choice_evidence.py`、`test_web_search_tool.py` |
| 模型任务入队后提交失败仍可能调用上游 | `ModelExecutionCoordinator` 使用 admission Future，提交成功才准许执行 | `test_model_execution.py` |
| 缺乏实际模型开销诊断 | 模型事件增加准备耗时、消息字符与数量、Tool 数量；评测收集有界数字指标 | `test_model_metrics.py` |

没有为具体外部项目或某个广告问句新增 Router 分支。现有词法选择器仍然是
启发式候选筛选，不是已证明普遍准确的语义理解器；不能因本轮通过几个改写句就
宣称意图识别全面达标。

## 检索证据契约

Run 响应新增 `knowledge_context`：

- `source=automatic_rag`，表示上下文路径，不冒充一次 `agent_knowledge_search` 执行。
- `documents` 只记录实际放入本轮模型上下文的文档 ID、来源、版本、摘要哈希与长度。
- 哈希覆盖经过脱敏和裁剪后实际交付的记录，不覆盖未发送的完整原文。
- `claims_answer_grounded=false`。送入来源不证明模型采用了来源，也不证明答案准确。
- 来源由服务端生成，并绑定当前 `run_id`；新 Run 在构建上下文前被拒绝时，
  不能沿用上一 Run 的检索证据。上下文本身构建失败时也会清空旧 advisory 数据，
  并记录失败阶段，再使用最小上下文继续。

评测新增 `knowledge_context_present` 与 `required_context_documents` 声明式断言，
并校验来源、哈希、大小和字段类型。原来的 `required_tools` 仍要求成功的实际 Tool
结果；没有修改既有 smoke/改写用例的断言来把自动 RAG 算作 Tool 通过。

Skill `knowledge-explainer` 升级为 `1.0.5`，补充明确检索请求、账户查询隔离和
证据外推边界。Skill 仍然只有 advisory 权限。

## 性能与验收边界

`model_metrics.attempts` 是 Harness adapter 尝试次数，不能当作 HTTP 请求数。
LLM adapter 内部重试应同时看 `usage.llm_requests`。准备时间和上游调用时间分开记录；
不记录 Prompt、工具参数或凭证。

预算分别约束 advisory 记录和 Catalog，不是整个模型请求的硬 token 上限。
实际模型样本仍可达到数万消息字符、十几到几十秒；本轮没有证明端到端 SLO 已达标。
离线知识检索速度也不能当作对话速度。

真实模型使用本机配置的 `agnes-3.0-flash`；广告渠道均离线，网页搜索为明确
simulated 的空结果 fixture，本地知识检索使用真实文档。原始逐场景结果位于
ignored `outputs/agent-quality-20261022/`；Git 只保存脱敏摘要。

本轮几次改写回归结果曾为 1/4、2/4、2/4。中间 smoke 为 8/8；参与修正的改写集
不是盲测，不与 smoke 平均，不覆盖重复抽样稳定性或大范围事实正确性。

最后一轮改写回归为 **3/4**。资料检索已有成功 Tool 证据，模糊创建请求正确进入
awaiting-input，能力介绍不再被强制触发查询。剩余失败是能力回答未提及已注册的
知识服务，原断言未放宽。人工检查还发现该回答对跨渠道操作能力有泛化描述；
本轮不把“有目录、有检索来源”当成“所有回答准确”的证明。

最后四个实际样本 P50 为 13973 ms、P95 为 34685 ms；消息峰值仍为数万字符。
因此这里只能确认增加了可定位开销的证据，不能宣称已实现普遍提速或完整稳定性。

最终 `make ad-agent-check` 通过，包含 2581 项测试、321 份 Tool 快照、Provider
契约审计和本地知识审计。额外的上下文与记忆聚焦回归 62 项通过，覆盖构建失败清空
旧数据；最终编译与 diff 检查通过。三个新/扩展控制模块的聚焦语句覆盖率为 94%。
全仓 qguard 仍为 FAIL、0 分、4960 项发现；没有关闭规则或把该门禁说成通过。

## 数据与回滚

没有执行数据库迁移，Schema 仍为 26。没有修改或替换本机聊天、模板、蓝图、
知识库与素材。未把本地数据库 sidecar、素材目录、配置秘钥或原始对话产物提交到 Git。
回滚只涉及代码和内置 Skill；不需要重建数据库。

既有权限、账户白名单、执行模式、确认、幂等和审计门禁保持不变。
没有调用真实广告 Provider，也没有自动重启正在提供 8766 服务的进程。
后续观测接入可以消费同一组 `model_start/end/error` 事件，无需改变 Tool 契约。

最终测试和模型复验数据记录在同目录日期对应的
`agents/evals/advertising/evidence/context-quality-20261022.json`。
