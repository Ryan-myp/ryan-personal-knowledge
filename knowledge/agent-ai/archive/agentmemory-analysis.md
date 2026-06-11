---

## 自测题

### 问题 1
Go 的 `sort.Slice` 和 C 的 `qsort` 有什么区别？

<details>
<summary>查看答案</summary>

1. Go 的 sort.Slice 是闭包排序，可以访问外部变量
2. C 的 qsort 需要回调函数，类型不安全
3. Go 的 sort 是 TimSort 变体，对部分有序数据优化
4. sort.Slice 是 Go 1.8 引入的，比 sort.Interface 更简洁

</details>

### 问题 2
为什么 agentmemory-analysis 要分析 memory 的使用模式？

<details>
<summary>查看答案</summary>

1. Agent 的 memory 增长是线性的，长期运行会 OOM
2. 分析使用模式可以找出 memory 泄漏点
3. 优化策略：滑动窗口、摘要压缩、定期清理
4. Go 的 GC 虽然自动，但频繁分配/释放仍会影响性能

</details>