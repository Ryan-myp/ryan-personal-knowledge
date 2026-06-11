---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
生产环境中 Token 计数为什么要在 Agent 层而不是 LLM API 层？

<details>
<summary>查看答案</summary>

1. API 层返回的 token 统计是单次调用的，不跨轮次
2. Agent 层可以累计整个对话的历史 token
3. 便于做预算控制和成本分析
4. 可以精确到每个 tool call 的 token 消耗

</details>

### 问题 2
Go 的 Cache 结构中 TTL 过期策略为什么不用定期清理？

<details>
<summary>查看答案</summary>

1. 定期清理需要后台 goroutine 持续运行
2. 惰性删除（Lazy Eviction）在 Get 时检查 TTL，零额外开销
3. 对于高并发场景，惰性删除减少锁竞争
4. 缺点是内存中可能有短暂过期的数据，但通常可接受

</details>