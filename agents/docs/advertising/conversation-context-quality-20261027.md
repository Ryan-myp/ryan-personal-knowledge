# 长对话与大结果上下文

## 边界

- `conversation_messages` 保留完整的脱敏会话；广告应用的 `conversation_digest`
  仍是有限字符的旧摘要。`conversation_state` 仅从用户显式陈述提取有来源的
  `constraint` / `decision`，最多八条、每条 240 字符。每条保留 `source_turn_id`
  与 `source_role=user`，重启时按 tenant、user、session 恢复。新话题或不相关续聊
  不注入旧约束；当前用户消息始终优先。
- `conversation_state`、Skill、历史召回均是 advisory。它们不能改变可信 principal、
  账户范围、执行模式、确认、幂等或 Tool 权限。旧 metadata 会被校验；格式不合法时
  降级为空。仍可能存在没有显式标记或被截断的约束，不能把此功能当作全量语义记忆。
- `ToolDefinition.result_summary_fields` 是只读列表 Tool 可选的发布者元数据。
  当前三个渠道的 `list_campaigns` 仅声明 `status`。Harness 只对**本次返回的行**
  计算分类计数；`scope=returned_page` 不代表账户全量。模型明细仍有
  `max_tool_result_chars` 上限，`context_truncated` 和 `context_count` 揭示截断；
  Provider 分页与原结果的 `max_output_bytes` 边界保持不变。汇总不能用于写 Tool，
  也不对预算、比率等数值做无业务语义的求和。

## 验证与观测

- 离线多轮评测案例在 `agents/evals/advertising/conversation_holdout_cases.json`。
  `run_conversation_regressions.py --model-backed` 需要显式配置评测模型，
  使用内存数据库、dry-run 与离线 Provider；不访问真实广告接口。
  回放模式不调用模型，只验证判定逻辑，不能证明实际对话正确率。
- `phase_metrics` 记录 Run 总耗时和 Tool 耗时之和，现有
  `model_metrics` 记录模型准备/执行耗时；Runner 输出每例及 p95。
  Tool 并发时耗时之和可能超过墙钟耗时，不应相减推导“其它阶段”。
  指标只包含数字，不保存输入/Tool 输出。线上仍需要实际模型/Provider
  分布与不同长度会话的分层采样，不能从单次本地基准宣称生产加速。
- 单进程回退旧代码不会修改完整会话表；新增 metadata 字段会被旧版本忽略。
  若需要回滚三个 Tool 的发布者元数据，须同步恢复相应的契约快照；
  已有对话正文及权限配置无迁移。
