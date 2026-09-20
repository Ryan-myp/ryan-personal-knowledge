# ad-agent 定时任务

定时任务是 Runtime 控制面能力，不是新的渠道 Agent。它只持久化：任务名称、五段 cron、时区、脱敏后的自然语言指令、会话/账户范围和安全 principal claims。

到期后 SchedulerService 通过共享数据库租约抢占一个 occurrence，并以幂等键 `schedule:{schedule_id}:{scheduled_for}` 提交普通 `agent.turn`。TaskExecutor 随后重新进入 `AgentRuntime.run()`，因此当时生效的 Skills、Tools、Tool Sources、权限、dry-run/live gate、ExecutionRun、ToolCall 和 Outbox 仍然是唯一执行边界。

## API

- `POST /schedules` 创建周期任务
- `GET /schedules` 查询当前 tenant/user 的任务
- `GET /schedules/{schedule_id}` 查询任务及最近触发记录
- `GET /schedules/{schedule_id}/runs` 查询触发记录
- `POST /schedules/{schedule_id}/pause` 暂停
- `POST /schedules/{schedule_id}/resume` 恢复并重新计算下一次执行时间
- `POST /schedules/{schedule_id}/run-now` 立即提交一次普通 Agent Task
- `DELETE /schedules/{schedule_id}` 删除任务及其 occurrence 记录

Chat 也支持 `schedule_create`、`schedule_list`、`schedule_pause`、`schedule_resume`、`schedule_delete` 和 `schedule_run_now`。调度指令中的 Meta/Google 业务动作不由 Scheduler 解释，而是在到期后由当前 Agent 根据 Skills/Tools 决定。

## 部署与恢复

SQLite 继续保持单进程约束。MySQL 使用 InnoDB 行锁和 `SKIP LOCKED`，多台 Runtime 可以同时运行 SchedulerService；同一个 `(schedule_id, scheduled_for)` 只会产生一个 occurrence。进程重启后，TaskExecutor 恢复 queued 任务，SchedulerService 根据未完成 occurrence 和幂等键继续提交，过期 lease 不会形成重复 Agent Task。

定时任务始终以 `dry_run` 创建，不保存一次性 live confirmation token。到期执行仍必须经过 principal、账户范围、Tool schema、幂等和审计边界。

系统运维 → 定时任务页面展示任务数、待执行/执行中/失败数、下一次执行时间、暂停恢复和最近触发记录；运行监控总览的 `schedules` 和 `instance.scheduler` 字段可供后续指标系统接入。
