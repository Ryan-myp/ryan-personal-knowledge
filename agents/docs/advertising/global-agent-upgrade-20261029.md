# 全局可靠性与上下文优化（2026-10-29）

本轮从 Skill 上下文、Run 结束、任务恢复、定时调度和管理页面的实际故障入手。
沿用单 Agent Runtime、通用 Run Kernel、已注册 Tool 和原持久化接口，没有另建
业务 Router，也没有加入按聊天关键词分流的特例。

## 已修复的问题

### Skill 编辑发布后的上下文一致性

此前，内置 Skill 先通过 Harness 注入，租户编辑后的同名 Skill 又经应用 Context
Provider 附加，两份规则可能同时进入模型。现在应用层的 `AdvertisingSkillCatalog`
先按租户组合不可变发布快照，同名发布版替代内置版，再复用通用选择器、参考资料检索
和 6,000 字符总预算。下线后恢复内置版，不修改共享目录，不影响其他租户。

新增可选 `build_request_context` hook，原 SkillCatalog 的 `build_tool_context` /
`build_context` 契约继续可用。组合目录最多缓存 32 个租户；发布快照或内置目录版本
变化即重建。Skill 仍然只是 advisory context，不能获得执行能力或绕开 Tool 门禁。

本地八组同名内置/托管 Skill 的固定样本，从合计 12,000 字符降为 6,000 字符。
100 次缓存读取中位耗时 0.0074ms，p95 为 0.0084ms。这仅测量目录组合输出，
**不代表整个 Prompt 减少一半，也不代表实际模型耗时或回答质量提升一半**。

### Run 终态与租约一致

此前 pipeline 完成时先写成功状态，Kernel 随后发现失租，只修正返回值，数据库可能
继续显示成功。现在由 Kernel 完成 heartbeat / release 清理后统一触发 Run 收尾，
仍在本地 Session 锁内，只更新当前 `run_id`。失租、release 拒绝或异常统一记录
`recovery_required`；迟到事件不能覆盖已结束 Run 的终态。

每次获取租约使用唯一 owner token，旧 Run 的迟到 heartbeat / release 不能影响
下一次 Run。直接使用 `SessionLease` 的原异常契约保留。pipeline 抛出的原始异常
继续抛出，收尾失败只附加脱敏的异常类型诊断，不假报成功。

### 任务与定时调度恢复

- 修复带 tenant / user scope 恢复任务时 SQL 绑定参数数量不匹配；读取和更新均验证身份范围。
- 定时任务已入队并绑定运行记录、但推进时间失败时，重试只校验原任务并推进游标，不再次提交。
- 对已绑定但不存在或不属于当前身份的任务，保留故障并拒绝重新提交，避免重复外部写入。
- 旧周期完成时不清除新周期的调度租约；既有 owner fence 继续生效。

这些是运行状态和恢复语义修复，不声称已撤回或回滚外部平台的操作。

### 知识管理分页与轻量读取

原界面只取前 100 条托管知识，再在浏览器分页，旧草稿无法翻到或搜索。现在由存储层
先筛选再分页，前端只显示当前页；正文仅在打开详情、编辑或复制时读取。

`GET /knowledge/documents` 新增 `source=all|builtin|managed`、`offset`、`q`、
`platform`、`category`；保留 `status`、`limit`。默认 source 为 managed，limit
上限仍为 200。响应包含 `documents / total / limit / offset / has_more / categories`。
列表不返回正文、Markdown 或 excerpt；身份和 `ads.read` 权限来自可信 principal。
托管内容的标题、正文和标签参与搜索，分类按 knowledge_type 筛选。

合并列表先排列内置 ID 升序，再排列托管 updated_at 降序、ID 升序。翻页失败保留原列表，
筛选条件变化时丢弃迟到响应，删除末页后最多补查一次新的末页。智能总结继续通过既有
已发布知识检索接口提供，不将其结果替换管理清单中的草稿。

### 管理页保存竞态

MCP / Skill 保存使用提交时的快照。保存期间继续输入时，保留新输入和未保存状态；
切到新草稿后，旧成功或失败响应都不能覆盖新草稿。MCP 保存成功后关联 server_id，
后续更新仍指向同一项。Skill 版本继续不可变，自动建议下个未用版本，保留手动版本选择。

## 验证与边界

隔离 Chromium 使用内存数据库与 125 条草稿，验证第 100 条之后的翻页、搜索和编辑，
模拟翻页 503、延迟保存及切换草稿；无浏览器异常。所有外部请求被阻止，没有调用广告
渠道或真实模型，也没有向正式数据库写入测试数据。

覆盖率统计针对本轮变更的 Python 可执行行，不代表全仓覆盖率。最终检查、服务回读和
质量扫描数据记录在 `agents/evals/advertising/evidence/global-agent-upgrade-20261029.json`。

最终 `make ad-agent-check` 退出码 0：3,498 项 Python 测试、256 项前端测试通过；
编译、328 个工具契约、能力审计、知识质量与检索基准、`git diff --check` 通过。
68 项聚焦回归覆盖变更可执行行 212 / 231，即 91.77%。存在一条上游 Starlette
测试依赖弃用警告，没有用真实模型或广告调用补测。

正式服务已使用原配置和原数据库重启，`*:8766` 监听、ready 正常。514 个会话、
14 个用户模板、5 个定时任务保留；核对最近 200 个会话 ID、全部模板和管理记录 ID，
没有缺失。354 个配置工具正常加载，86 条内置知识可分页读取。正式页面的只读浏览器
验收通过翻页和正文详情，无页面异常、无测试写入；隔离服务 18767 已关闭。

严格 QGuard 仍未通过：全仓存在大量历史告警，增量保留 Kernel 的两处通用 Exception
标记。它们位于受信任扩展调用的统一异常边界：一处收尾后重抛原错，另一处将收尾错误
附加到原错。未通过缩小必要异常范围、添加忽略规则或降低阈值使扫描表面通过。
本次全仓扫描 785 个文件、4,994 项发现、评分 0；变更 Python 文件的发现数从
160 降为 157，但仍有上述两处新标记，因此增量严格门禁也未通过。

## 部署、恢复和后续工作

无 schema 迁移，不变更账号范围、凭证、live 开关或原数据位置。前后端需要一起更新，
继续使用原 LaunchAgent、`config.test-live.yaml` 和 `agents/ad_agent/ad_agent.db`，
监听 `0.0.0.0:8766`。服务更新前备份 SQLite，更新后核对原会话、模板和管理内容。
回滚时恢复上一版完整代码并使用原配置启动；不需要删除知识、Skill、模板或恢复旧 DB。

本轮修复的是可复现的工程故障，没有扩大线上广告类型验收结论，也没有测量真实模型的
意图识别准确率。既有日志、runtime_signals 和管理错误提示已能反映这些恢复状态；
更完整的租约恢复告警和线上趋势可继续接入统一观察性接口，不阻塞本轮修复。

## 复核入口

```bash
make ad-agent-check
make ad-agent-quality-delta
```

聚焦回归文件包括 `test_tenant_skill_context.py`、`test_builtin_skill_editing.py`、
`test_knowledge_management_pages.py`、`test_task_recovery_scope.py`、
`test_run_lease_finalization.py`、`test_schedule_recovery_fencing.py`，以及前端
`test_management_save_races.js` 和 `test_knowledge_management_pages.js`。
这些回归使用内存或临时存储、假模型和受控响应，不需要平台凭证。
