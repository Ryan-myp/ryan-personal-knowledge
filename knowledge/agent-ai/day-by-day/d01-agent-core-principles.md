3. 工具返回了什么？
4. LLM 怎么组合信息给出答案？
---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
Go 的 goroutine 泄漏怎么排查？

<details>
<summary>查看答案</summary>

1. 用 pprof 分析 goroutine 数量
2. `runtime.NumGoroutine()` 持续监控
3. 检查 channel 是否有人接收
4. 检查 context 是否正确传递和取消
5. 常见泄漏场景：goroutine 阻塞在 channel 写入/读取、死锁

</details>

### 问题 2
Agent 的主循环中 `planAction` 返回 "finalize" 代表什么？

<details>
<summary>查看答案</summary>

1. 表示 Agent 已经收集了足够信息
2. 不再需要调用工具，直接输出最终答案
3. 避免不必要的 API 调用，节省 token
4. 这是 ReAct 模式的终止条件之一

</details>