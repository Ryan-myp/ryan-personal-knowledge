# Agent 质量与稳定性迭代

日期：2026-10-22。

本轮不改变单 Agent / Harness / Tool 门禁，不访问真实广告 Provider。
优化范围为知识检索、反馈回归、存储职责和本地故障恢复验证。

## 实现边界

| 要求 | 实现位置 | 验收证据 |
| --- | --- | --- |
| Embedding 超时不产生无界积压 | `agent_platform/data/embedding_runtime.py` | 超时后槽位保持占用，底层调用退出才归还 |
| 临时失败可恢复、租户故障不互相污染 | `applications/advertising/knowledge/semantic_retrieval.py` | 范围级退避、查询重试、模型切换回归 |
| 查询不反复读取、解析整张向量表 | `agent_platform/data/persistent_semantic_index.py` | 版本化快照、LRU、标量预算、跨实例重建失效 |
| 命中词与覆盖率属于各自文档 | `applications/advertising/knowledge/ranking.py` | 多文档排名回归 |
| 反馈能转成可执行验收 | `agent_platform/evals/regression.py` | 闭合声明式断言、未评分与失败分开 |
| 反馈审核可录入并导出断言 | feedback service / API / Chat 反馈审核面板 | 权限、租户、存储和静态交互测试 |
| MySQL 存储各职责独立 | `persistence/mysql_{pool,connection,sql,migrations,store}.py` | 既有存储测试及新的取消、关闭、迁移回归 |
| 检索质量和延迟进入常规检查 | `make ad-agent-check` | 知识审计、检索评测、缓存性能基准 |

以上文件均在 `agents/` 下。MySQL 的旧内部实现不保留 import shim，调用方和测试使用所属模块。

## 检索行为

Embedding 阻塞调用使用进程共享的有界执行器。调用超时只结束等待，不宣称已经终止
上游请求，也不会提前归还并发槽位。容量耗尽时检索回退词法路径。

错误按知识范围记录，经过短暂退避可以重新查询，不再因一次临时失败永久关闭整个
进程的语义检索。相同模型下的查询向量可在内置和当前租户范围复用；文档结果仍按
各自 scope 检索，缓存不跨租户返回文档。

索引持久数据仍通过 PersistenceBackend 管理。查询先检查 fingerprint、更新时间、
维度和记录数，再复用归一化快照。外部重建使旧快照失效；加载期间检测到版本改变，
本次语义查询失败并回退，不返回混合版本。缓存受 scope 数和标量总量约束，超过
本地预算的索引不装入内存。

本轮没有实现 ANN，也没有接入新的向量数据库。计算仍是有界精确余弦匹配，
通过归一化缓存和 top-k heap 降低重复 I/O、解析和全量排序开销。

## 反馈回归闭环

审核人可以保存自然语言期望，以及以下固定断言：

- 必须成功调用的工具、禁止调用的工具、实际调用次数上限。
- 回复非空、必须包含或不得包含的文本。
- 预期 intent、是否需要补充输入、是否需要确认。

断言不支持命令、脚本、动态正则或自定义 judge。所需 Tool 的判断来自实际成功结果，
不能用计划中出现 Tool 代替实际调用。缺少可执行断言的样例标为 `ungraded`，
不能通过回归发布门。

导出 schema 为 `ad-agent-regression-cases/v2`，保留人工期望并增加断言和可执行标记。
报告不复制回复全文或上游异常正文。

运行入口：

```bash
# 只重放已有响应证据，不调用模型或广告 Provider。
./scripts/ad-agent-python scripts/advertising/run_conversation_regressions.py \
  --cases path/to/reviewed-cases.json --responses path/to/responses.json \
  --output outputs/conversation-regression/replay.json

# 显式调用已配置的评测模型；广告 Provider 仍使用既有 Skill-up 离线执行配置。
./scripts/ad-agent-python scripts/advertising/run_conversation_regressions.py \
  --cases agents/evals/advertising/conversation_regression_cases.json \
  --model-backed --output outputs/conversation-regression/model.json
```

模型模式沿用 `AD_AGENT_EVAL_MODEL`、`AD_AGENT_EVAL_API_KEY` 和
`AD_AGENT_EVAL_BASE_URL` 的可信部署配置。评测数据不能设置凭证、命令、执行模式或账户范围。
八个内置对话场景涵盖问候、能力介绍、知识查询、外部资料、流程图、只咨询预算和缺参创建。
本轮只验证评测管道，不声称已经完成这些场景的真实模型效果测量。

## 存储与恢复

Schema 26 只给反馈表增加 `assertions` 字段，不删除、覆盖历史聊天、知识或模板。
旧反馈默认没有自动验收断言，需要人工补全。MySQL 的 LONGTEXT 插入显式提供值，
不依赖后端不支持的文本默认值。

MySQL 事务通过连接层的 transaction context 管理。语句被取消、中断或抛错时回滚，
回滚再失败时保留主异常，并丢弃失效连接；清理注释和日志仅包含异常类型。
连接池关闭后，等待线程不能重新打开连接；关闭失败计数可检查。

回滚代码不需要删除 Schema 26 字段。需要回滚部署时保留新增字段和已审核断言，
不要降级、重建或替换数据库。语义缓存是进程内派生数据，可丢弃，SQL 快照保留。

## 本地证据与限制

- `make ad-agent-check` 完整运行通过：2502 项测试、编译、320 个 Tool 契约快照、
  知识质量检查与向量缓存基准。其后补充的回复非空断言也通过了相关回归测试。
- 既有独立进程验证脚本本轮实际运行，五个场景通过：Session 租约、任务争抢、
  Worker 进入统一 Runtime、Worker 心跳和退出、崩溃后的显式恢复。
- 证据为本机临时 SQLite 共享持久化，不是生产集群部署证明，Provider 调用为零。
- 63 个检索用例、83 个文档、541 个 chunk：词法 Hit@3 为 1.0，MRR 为 0.958，
  Recall@3 为 0.883，nDCG@3 为 0.878；一次本地 P95 约 34 ms。
- 2000 条 64 维合成向量、20 次热查询：一次本地 P95 约 6 ms，
  向量快照只加载一次，重建索引对象后排名一致。
- 词法延迟不包含真实 Embedding 网络请求；合成 Embedding 只验证契约，
  不能当成真实语义模型的拒答准确率或广告业务效果。
- 全仓 qguard 的历史问题不通过本轮拆分自动消失，仍需独立报告，不能用局部评分
  替代全仓通过。广告 Provider 的历史失败、跳过项也不在本轮冒充已修复。
- 本轮五个重点模块（Embedding 执行器、持久语义缓存、回归断言、排名、语义检索）
  的语句覆盖率合计 93%，单模块 88%–98%，不代表全仓覆盖率。

继续使用现有结构化状态与结果字段，不为本轮引入新的观察性平台依赖。
