---

## 自测题

### 问题 1
Go 的 `map` 遍历顺序为什么不确定？

<details>
<summary>查看答案</summary>

1. Go 设计有意打乱 map 遍历顺序，防止依赖遍历顺序的代码
2. 内部实现中，key 的哈希值决定了桶的位置
3. 如果需要有序遍历，应该用 slice + sort
4. 这在测试中会导致不确定的行为，所以不能依赖

</details>

### 问题 2
agentmemory-integration 中为什么推荐用 SQLite 而不是 Redis？

<details>
<summary>查看答案</summary>

1. SQLite 是嵌入式数据库，零运维，适合 Agent 本地部署
2. Redis 需要单独部署和维护，对小型项目过重
3. SQLite 支持复杂的查询（FTS5、JOIN），适合知识图谱
4. Go 的 `database/sql` 标准库对 SQLite 有优秀的支持

</details>