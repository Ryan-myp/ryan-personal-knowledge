---
reference_scope: [DV360, Display & Video 360]
---

# DV360 报表解读

DV360 Line Item 报表为空、查询失败或需要恢复时，先区分账户投放资源与
报表证据。当前已注册的
`dv360_get_line_item_report` 仅接受 `advertiser_id`、
`line_item_id` 和日期输入；**不提供 Campaign-level report**，
也不能凭 Wiki 的理想化报表流程推断当前 Tool 可创建或下载
任意维度的异步报告。先查 Registry 和具体 schema，再承诺动作。

## 先验口径

固定可信 Advertiser、Line Item ID、日期/时区、币种、数据来源与
`report_context` 完整性；同一 Line Item 的展示、花费、转化也要区分
投放状态、报告生成时间和转化成熟时间。若 `account_timezone`、
`account_currency` 或归因设置未返回，标为 Unknown，不从其他账户补齐。

## 空报表与失败恢复

1. 检查查询是否成功、是否 live、过滤日期是否与 Line Item 排期重合。
2. 通过只读对象详情确认 IO/Line Item 的状态、预算、定向、库存和
   Creative 审核；对象存在不等于已发生展示。
3. `empty` 表示本次查询未返回行，不能直接写成“零花费”；
   `possibly_truncated` 不能用于完整 Campaign 汇总。
4. 当用户提供外部异步报告时，要核验任务 ID、完成状态、范围、
   快照/下载时间和行数；任务仍 pending 或结果下载失败时先对账，
   不把它转换为零，也不盲目重复创建报告。
5. 给出证据、未知、下一次只读核对项和恢复条件；不要将平台归因
   表现等同于增量。

跨渠道比较要先对齐币种、日期时区、资源粒度、事件定义和归因窗口。
更多方法背景见 Wiki `dv360-report-query-and-async-recovery`。
