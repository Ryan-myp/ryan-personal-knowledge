---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
Agent 的可观测性为什么需要 Tracer + Logger 两套系统？

<details>
<summary>查看答案</summary>

1. **Tracer**：关注调用链和性能，记录每个 Span 的耗时
2. **Logger**：关注事件和异常，记录 INFO/ERROR 级别日志
3. Tracer 用于性能分析和瓶颈定位
4. Logger 用于故障排查和安全审计

</details>

### 问题 2
Go 的 pprof 和自定义 Tracer 在 Agent 监控中各有什么作用？

<details>
<summary>查看答案</summary>

1. **pprof**：系统级监控，goroutine/内存/CPU 使用
2. **自定义 Tracer**：业务级监控，每个 Agent step 的耗时和状态
3. pprof 适合排查性能问题（慢查询、内存泄漏）
4. Tracer 适合排查业务问题（哪个 step 卡住了、哪个 tool 失败了）

</details>