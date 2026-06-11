---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
RAG 优化中，Reranking 为什么比单纯增加 topK 效果更好？

<details>
<summary>查看答案</summary>

1. topK 增大引入更多噪声文档，降低回答质量
2. Reranking 用更精细的模型重新打分，保留高质量文档
3. 成本可控：先粗筛再精排，比全量精排便宜
4. 实际效果：topK=10 + rerank → top3，比 topK=50 效果还好

</details>

### 问题 2
Go 中怎么实现高效的 Reranking？

<details>
<summary>查看答案</summary>

1. 用 batch 方式并行处理多个文档
2. 关键词匹配作为快速筛选，减少 rerank 调用
3. 结果排序用 O(n log n) 的 sort.Slice
4. 可以缓存 rerank 结果，相同 query 复用

</details>