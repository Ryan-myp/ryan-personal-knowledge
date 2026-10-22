# 通用执行与模型质量复验

本轮在 `ffaf706` 之后实施。保持一个 Harness Runtime、既有 Tool 权限门禁，
不创建广告专用执行器。没有向真实广告 Provider 发送请求。

## 需求与实现

| 要求 | 归属 | 验收 |
| --- | --- | --- |
| 提交失败不泄漏 Embedding 槽位 | `agent_platform/data/embedding_runtime.py` | 直接提交失败、入队后提交失败、超时、关闭与恢复回归 |
| 评测响应不做布尔类型猜测 | `agent_platform/evals/regression.py` | 字符串、数字、null、数组与对象不能冒充布尔证据；缺失字段不能证明 false |
| 只读 Tool 有界并发 | `agent_harness/tool_execution.py` | 显式 read + safe/idempotent 才并发；写、交互和未知副作用为串行屏障 |
| 等待用户时不执行后续写入 | Harness 与结果投影 | 后续调用标为 deferred，不伪装成执行结果 |
| 缺少目标时结构化澄清 | `agent_platform/tools/clarification.py` | `agent_request_input` 产生 awaiting_input；问题与选项能通过现有界面协议展示 |
| 能力介绍覆盖注册的通用功能 | 广告 capability catalog / profile | 优先保留通用 Tool，明确能力提问不只摘取最前几个 Skill |
| 缩小持久化职责 | persistence facade / repositories | 原有接口签名、锁范围与 SQL 行为保持；schema 与 26 个迁移分离 |
| 检索排名进入门禁 | `validate_knowledge_quality.py` | Hit@3 与 MRR 都要求至少 0.95，保留负例、平台边界与 top1 验收 |

## 并发与安全

广告组合默认使用 `parallel_reads`，单 Run 并发默认 2，全应用 in-flight Tool 默认 8，
可以通过组合参数调整。上限需要满足 `1 <= parallel <= inflight <= 64`。
各 Provider 原有的限流、账户范围和权限检查继续生效。

写操作不会因为新的模式而并行；显式依赖仍由 Harness 解析。交互、确认或终止
结果阻止后续组继续执行。未执行的调用保留 deferred 标记，但不进入广告界面中
代表实际操作结果的 `results` 列表。

Clarification 是无外部副作用的读取类 Tool，不接受账户身份、凭证或执行命令。
它只生成问题和选择项，不替用户授权或选择账户。交互工具可以出现在模型可见
列表，但不能污染业务目标命名空间。显式蓝图、已明确的只读发现和权限拒绝路径
继续使用原有工具选择边界。

## 持久化归属

在 `agents/applications/advertising/persistence/` 中：

```text
store.py                 # 公共 facade、连接生命周期、剩余执行状态接口
schema.py                # 唯一 schema 与版本
sqlite_migrations.py     # 显式版本迁移
knowledge_store.py       # 文档、原始来源、发布与 FTS
memory_store.py          # 记忆与召回
session_store.py         # 会话、租约、聊天历史
extension_store.py       # Skill、Plugin、MCP 控制面记录
workflow_store.py        # Campaign 与业务工作流
transitions.py           # 工作流状态转换约束
```

Repository 共享 facade 提供的连接和锁；没有新建连接池或改变锁范围。
MySQL 仍使用其版本化连接适配器，domain repository 不直接 import MySQLStore。
本轮 schema 仍为 26，没有新建数据库或清空历史数据，也没有旧路径 import shim。
回滚代码时保留现有数据库与 Schema 26，不需要复制或重置数据库。

## 真实模型验证

使用本机配置的 `agnes-3.0-flash`，实际发送模型请求。广告 Provider 离线，
网页搜索使用明确标为 simulated 的空结果 fixture，知识查询使用真实本地知识库。
该配置验证意图、工具使用、澄清与回答边界，不证明外部 API 或实时搜索可用性。

同一组 8 个 smoke 场景依次观察到 6/8、7/8、8/8 通过。
没有为具体问句增加 Parser 或 Router 关键词分支。发现和修复的行为包括：

- 能力介绍只选择最前几个 Skill，漏掉了已经注册的知识检索。
- 没有平台和目标的创建请求擅自进入某个渠道模板列表。
- 澄清 Tool 加入可见列表后曾污染账户解析命名空间，已通过独立回归隔离。

最近一次 smoke 样本 P50 为 14944 ms，P95 为 78715 ms。
样本少、模型服务有波动，不能据此宣布生产 SLO；本地检索的毫秒级数字也不是
完整对话延迟。对应脱敏报告保存在 `outputs/agent-quality-20261022/model-recheck/`。
独立改写问法位于 `agents/evals/advertising/conversation_holdout_cases.json`，
结果单独保留，不用于把 smoke 通过率描述为普遍准确率。

独立改写问法首轮实际通过 2/4，失败情况没有放宽断言或隐藏：

- 能力范围的另一种问法触发了额外知识查询，违反了该 case 的零工具调用要求。
- 泛化“查资料”问法未返回指定知识 Tool 的执行证据。回答可能使用了自动注入的
  知识上下文，不能仅凭此判断事实错误，但当前评测不足以证明检索路径满足约定。

能力问法定位到一个选择器缺陷：可见的通用语义发现 Tool 被无条件当作强制执行依据。
已收紧为明确知识检索、追问和需要实时证据的网页查询；本地知识上下文的可用性
不再自动强制额外查询。没有增加“工作台”或某个问句的路由关键词。

修复后该改写集复测为 3/4，仍保留“查资料”未满足指定知识 Tool 执行证据的失败。
该集参与修正后已是回归集，不再当作未见泛化测试。不能将它与 smoke 的 8/8 平均
来掩盖剩余项。
可入 Git 的脱敏摘要保存在 `agents/evals/advertising/evidence/quality-followup-20261022.json`；
原始逐 case 回复不提交。

## 评测口径

知识检索用例的 `expected` 是可接受参考文档集合，不是强制要求全部召回。
所以基于该集合的 Recall@3 和 nDCG@3 是排名诊断指标，不能直接当成整个广告行业
知识覆盖率。报告明确输出该语义，门禁现在同时检查 MRR，防止只有一条低位命中也通过。

模型回归报告区分 real-model/offline-provider 与 replay，新增实际执行样本的
P50/P95 延迟；人工未填写断言的 case 仍是 ungraded，不视为通过。

## 验证边界

- 本机通用 Run 测量：100 次、8 并发、零失败，P95 约 18 ms。模型是 1 ms 本地替身，
  不是实际模型容量或生产吞吐。
- 五个独立进程恢复场景重新执行并通过，Provider 调用为零，不是生产集群验收。
- 三个重点控制模块的语句覆盖率为 94%，不是全仓覆盖率。
- 全仓 qguard 仍未通过。部分动态 SQL 发现对应已参数化的值和服务端封闭字段集合，
  但不会因此关闭扫描规则或将全仓标为通过；其他历史发现也未在本轮全部清理。
- 广告 Provider 原有实测缺口不在本轮宣称解决；本轮未重启已有的 8766 服务。
- 最终 `make ad-agent-check` 通过 2540 项测试，321 份 Tool 契约快照有效，
  包含澄清选项 UI 协议、只读并发和强制 Tool 选择边界的回归。
