# 任务可靠性升级与验收边界

本轮按任务级质量、长对话、运行恢复、广告复盘、体验性能五个方向完善。保持单 Agent
Run Kernel 与既有注册 Tool 执行链路，不增加渠道 Router，也不引入另一套 Run 生命周期。

## 实现与验收对应

| 要求 | 所属层 | 验收证据 |
|---|---|---|
| 任务按全过程判断 | 平台 evals `task_quality.py`；广告 Skill-up 适配器 | 中间轮错账户、禁止工具、缺少回合证据均失败；不输出原始回复到评测摘要 |
| 长对话验证 | `conversation_holdout_cases.json` | 30/40/50 轮预算修订、约束撤销、话题切换及恢复讨论；总输入仍限制 30000 字符 |
| 发布依赖当前版本 | 平台 evals `task_release.py` 与 readiness policy | 源码/上下文/评测程序与数据集摘要匹配、7 天内、完整三次成功；局部复测不能拼接为通过 |
| 中断与租约恢复 | 持久化 `run_recovery.py`；通用 EventRepairConsumer | 有效 Session/Task 租约保护；每批最多100项；仅标记未知结果，禁止自动重放 |
| 复盘引用真实证据 | 应用 `optimization_report_evidence.py` | 核验可信 principal、账户、资源、唯一调用、成功 live 输出、完整报表、实际指标字段和日期 |
| 体验指标 | Harness `run_experience.py` | 首次工具进度、首次文字、整轮耗时、模型调用次数、Prompt 字符峰值，均为有界数值观测 |

## 对外接口变化

- `agent_create_optimization_review`、`agent_update_optimization_review` 升级到 1.1.0，增加可选
  `baseline_evidence` / `outcome_evidence`。原输入仍兼容，旧手工记录明确标记 `user_supplied`。
- 报表证据引用包含 `session_id`、`turn_id`、`tool_name`、`row_index`。`measurement.metric`
  必须是原报表字段路径，例如 `cpc` 或 `metrics.cost_micros`，不接受任意计算公式或别名。
  当前只核验单个资源的一行直接指标；同资源多行分段、截断列表和相对日期需要先补足数据。
- 复盘保留 `baseline_provenance`、`outcome_provenance` 和 `context_gaps`。当前报表没有完全
  规范化单位、币种、时区、归因窗，不能将模型填写的口径提升为可信事实。
- `/monitoring/overview` 增加 `recovery`：当前身份的 Run/Task/Workflow 待核验列表、总数和下一步动作。
  列表最多30项；`has_more` 标记剩余记录。详情沿用各自受权限和租户隔离保护的读取 API。
- 运维页面增加响应耗时表和待核验记录表，详情只读，切换记录时拒绝旧请求覆盖新选择。
- Task 恢复 API 使用 `operator_attested=true`，不再接受名为 `provider_verified` 的客户端声明。
  `ads.reconcile` 操作员确认已核对外部状态后才能重新排队；持久化审计记录操作人、引用和时间，
  明确区分人工核验与系统通过只读 Tool 完成的 Provider 回查。
- 原生对话 Tool 执行现在同步保存脱敏调用审计，使用本次调用实际解析的账户；不从会话的
  旧账户反推执行目标。审计保存失败会使调用明确失败，未知写入仍沿用统一恢复门禁。
- `/monitoring/agent-runtime` 的 `metrics.experience` 提供最近最多256个已结束 Run 的 P50/P95，
  不存储回复、推理内容、工具参数或凭证。计时从 `agent_start` 开始，不含排队等待；未产生文字
  的 Run 不伪造零延迟。首次进度定义为工具开始或正文输出，不把固定“正在处理”当作有效输出。
  `prompt_chars_peak` 统计模型消息正文的字符峰值，不含 Tool schema 序列化，也不是 token 数。

## 评测与发布

普通 `make ad-agent-check` 仍然离线，不调用渠道或模型。真实模型质量单独显式运行：

```bash
# AD_AGENT_EVAL_MAX_P95_MS 必须由部署负责人设置为完整多轮任务的耗时门槛。
make ad-agent-model-quality
./scripts/ad-agent-python scripts/advertising/release_readiness.py \
  --profile release --conversation-evidence outputs/conversation-model-quality.json
```

`ad-agent-model-quality` 使用已配置模型，Provider 始终离线，完整任务重复三次。输出同时区分
整项多轮任务耗时与单轮耗时。`--conversation-evidence` 本身只读已有报告，不触发模型调用。
release 仍保留其他原有门禁；通过 task_quality 不意味着广告 Provider 或生产发布已通过。

长任务集是仓库公开回归集，不应声称为未知留出集。脚本模型的通过只证明执行和评测契约，
不证明真实模型的语义准确率。新增用例需要完成真实模型运行后才能形成准确性结论。

## 恢复、权限与回滚

- 本轮不自动重排历史任务，不调整广告，不批量审核反馈，也不把待核验状态改成成功。
- 每次恢复检查先处理事件补写，再按租约判断失联 Run；同一事务保存恢复事件与状态。
  无有效 Run 的过期 Session 租约可以释放，新的调用仍通过 Run Kernel 重新获得租约。
- 报表证据只能读取当前 principal 拥有的会话，且账户仍须位于其 scope 中；新增逻辑不会调用
  Provider client，真实执行与回读继续使用既有权限、live、确认和幂等链路。
- 无数据库 schema 迁移。新增 JSON 字段是兼容扩展。Task 恢复 API 请求字段有调整，旧字段
  `provider_verified` 会被拒绝，调用方需改用 `operator_attested`。回滚时还原本轮代码及 Tool snapshot；
  已记录的真实审计和恢复状态应保留，不恢复旧数据库覆盖新对话。
- 当前数值指标为进程内窗口，重启清空。后续可通过既有 MetricsSink 接入持久化时序系统，
  不需要修改 Tool 契约。

## 尚不能宣称完成的部分

真实模型完整三次长任务评测、历史未知副作用的 Provider 回查、真实广告成熟观察窗内的收益
验证，需要独立执行与真实证据。本轮不会把离线审计夹具、机制建设或前后变化当成这些结果。

## 本轮检查

- `make ad-agent-check`：3620 项 Python 测试、269 项前端测试通过，328 项 Tool 契约与86篇
  知识页检查通过；UI 最后调整后重新运行269项前端测试通过。
- 五个新增核心模块的定向语句覆盖为277/305，约90.82%；五个模块独立静态质量门禁通过。
- 全仓静态质量门禁仍未通过，未降低阈值或把模块级结果当成全仓结果。
- 本地 readiness 通过；任务真实模型证据明确为 `not_verified`。
- 原8766服务使用原配置与数据库重启，保留515个会话、14个模板、5个定时任务。失联运行数和
  过期 Session 租约均为0；12项历史未知执行保留待核验，运营总览仍为 critical。

## 2026-10-31 恢复闭环跟进

- 监控恢复列表现在统一包含 Run、Task、Workflow；总数和列表使用相同的租户/用户范围。
  Workflow 详情通过现有只读 API 加载，不自动回查或重放 Provider 操作。
- Task 恢复请求从 `provider_verified` 改为必填 `operator_attested=true`。它表示有
  `ads.reconcile` 权限的操作员确认已核对外部状态，不表示系统已自动验证 Provider。
  审计记录保留操作人、引用和声明时间；引用在持久化前做凭证形态脱敏。旧请求字段被拒绝。
- 无 schema 迁移、无历史任务重排，也没有调用任何真实渠道 API。回滚只需回滚代码；
  已写入的 `recovery_attestation` JSON 会保留，不应覆盖运行数据库。
- 最终 `make ad-agent-check`：3807 项 Python 测试、284 项前端测试及工具、创建契约、
  知识库审计全部通过；`make ad-agent-quality-delta` 无新增静态问题。
- 全仓 qguard 仍有历史质量债务：797 个文件、4988 项既有发现；本次增量门禁未发现新增项。
- 真实模型完整三次长任务评测仍未验证；Google/TikTok/DV360 部分广告格式或资源仍处于
  部分/计划状态。本次离线补齐不能替代模型验收或渠道实测。

结构化证据见 `agents/evals/advertising/evidence/task-reliability-upgrade-20261030.json`。
