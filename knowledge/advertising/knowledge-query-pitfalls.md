# Knowledge Query Pitfalls

## 已知坑

1. **scenario_card min_confidence_score=999** 不走 knowledge_card 快捷路径
   - 诊断：检查 source_mode 是否为 `sqlite_candidate_subgraph`
2. **render_answer_context 的 api_docs 优先级问题**
   - 误匹配会覆盖正确 code 结果
   - 临时绕过：使用 `--scope code`
3. **extract_intent 对短中文置信度低**
   - 保留自定义 `get_scope_weights()` 作为补充
4. **目录名必须用下划线**（knowledge_search/ wiki_engine/）

## 调试方法

```bash
# 1. 检查 query 是否正确路由到 knowledge_card
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Redis cluster 怎么搭建", "scope": "code"}'

# 2. 检查 scenario_card 是否命中
# 查看 response 中的 source_mode 字段

# 3. 检查 API 文档匹配
# 查看 render_answer_context 中的 api_docs 字段
```

## 相关资源

- ad-ai-coding 仓库: git.garena.com/marketing/ad_ai_coding
- query_knowledge.py 路径: ~/ad_ai_coding/tools/knowledge_query/

---

## 自测题

### 问题 1
为什么 `min_confidence_score=999` 会绕过 knowledge_card 快捷路径？

<details>
<summary>查看答案</summary>

1. **高阈值**: 999 的置信度阈值几乎不可能命中
2. **降级机制**: 命中失败时走通用知识卡片逻辑
3. **source_mode**: 此时 source_mode 会是 `sqlite_candidate_subgraph` 而非 `knowledge_card`
4. **实际影响**: 通用卡片逻辑不处理广告平台 API 查询，导致返回通用结果

</details>

### 问题 2
Go 中如何实现一个高效的 knowledge card 缓存？

<details>
<summary>查看答案</summary>

1. **LRU 缓存**: 用 map + doubly linked list 实现 O(1) 增删查
2. **TTL**: 过期知识自动清理，避免返回过时信息
3. **并发安全**: sync.RWMutex 允许多读单写
4. **预加载**: 启动时预加载高频知识卡，减少查询延迟
5. **内存限制**: 设置最大条目数，超出时驱逐最久未用的

</details>