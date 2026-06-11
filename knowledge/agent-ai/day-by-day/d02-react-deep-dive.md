**观察**: 随着 history 增长，token 消耗快速增长。5 步后成本明显上升。
---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
Go 的 `sync.Mutex` 和 `sync.RWMutex` 在 Agent 场景下如何选择？

<details>
<summary>查看答案</summary>

1. Agent 的 memory 是读多写少场景
2. `RWMutex` 允许多个 goroutine 同时读取 memory
3. `Write` 需要独占，但 `Read` 不阻塞
4. 如果只用普通 Mutex，所有读操作都会串行化，性能差

</details>

### 问题 2
ReAct 模式中的 Thought 和 Observation 分别存储在哪里？

<details>
<summary>查看答案</summary>

1. Thought 是 Agent 的内部推理，存在 Agent 的 memory 中
2. Observation 是工具执行的返回结果，也需要存入 memory
3. 两者共同构成 Agent 的历史上下文
4. 实际系统中，Thought/Observation 也常存入日志系统用于调试

</details>