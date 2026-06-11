---

## 自测题

### 问题 1
biz-delivery 框架中为什么用 knowledge-search 而不是直接查数据库？

<details>
<summary>查看答案</summary>

1. **语义搜索**：knowledge-search 支持自然语言查询，数据库只支持精确匹配
2. **混合检索**：BM25 + 向量检索，比单一检索效果好
3. **跨代码库**：knowledge-search 可以搜索代码、文档、数据库
4. **性能**：knowledge-search 做了缓存和预计算，查询更快

</details>

### 问题 2
Go 在 biz-delivery 框架中相比 Python 的优势是什么？

<details>
<summary>查看答案</summary>

1. **性能**：Go 编译型语言，查询性能比 Python 高 10 倍+
2. **并发**：goroutine 天然适合高并发查询场景
3. **部署**：单二进制文件，无依赖，容器化简单
4. **团队**：团队技术栈是 Go，统一语言降低维护成本

</details>