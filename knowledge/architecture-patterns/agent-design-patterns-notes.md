---

## 自测题

### 问题 1
为什么 Agent 设计模式的"反思"（Reflection）机制对生产环境很重要？

<details>
<summary>查看答案</summary>

1. **自我修正**：Agent 可以分析自己的错误输出并调整
2. **质量保障**：减少幻觉和错误决策
3. **学习循环**：通过反思积累经验，越用越好
4. **监控指标**：反思过程本身就是可观测的日志

</details>

### 问题 2
Go 的反射（reflect）和 Agent 的反射（Reflection）有什么本质区别？

<details>
<summary>查看答案</summary>

1. **语言反射**：reflect 包操作运行时类型，是底层机制
2. **Agent 反思**：LLM 自我分析输出，是语义层面的
3. **性能**：reflect 有运行时开销，Agent 反思有 LLM 调用成本
4. **用途**：reflect 用于元编程，Agent 反思用于自我改进

</details>