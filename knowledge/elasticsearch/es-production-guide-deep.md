# Elasticsearch 生产环境实战指南

> 深入 Elasticsearch 生产部署：集群设计、分片策略、查询优化、运维实践。

---

## 1. 集群架构设计

### 1.1 节点角色

```
┌─────────────────────────────────────────────────────────────────┐
│                     ES 节点角色                                 │
├─────────────────────────────────────────────────────────────────┤
│  Master Eligible Nodes (master 候选节点)                       │
│  ├── 参与 master 选举                                           │
│  ├── 存储集群状态                                               │
│  └── 建议: 3-5 个                                               │
│                                                                 │
│  Data Nodes (数据节点)                                          │
│  ├── 存储数据分片                                               │
│  ├── 执行 CRUD/搜索操作                                         │
│  └── 建议: 根据数据量扩展                                       │
│                                                                 │
│  Coordinating Nodes (协调节点)                                  │
│  ├── 接收请求，分发到数据节点                                   │
│  ├── 聚合结果，返回客户端                                       │
│  └── 建议: 独立部署，避免资源争用                               │
│                                                                 │
│  Ingest Nodes (摄取节点)                                        │
│  ├── 预处理文档（管道处理）                                     │
│  └── 建议: 高写入场景使用                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 分片策略

```yaml
# 索引模板配置
PUT _index_template/my-template
{
  "index_patterns": ["logs-*"],
  "template": {
    "settings": {
      "number_of_shards": 5,
      "number_of_replica_shards": 1,
      "refresh_interval": "30s",
      "translog": {
        "durability": "async",
        "sync_interval": "5s"
      }
    }
  }
}
```

---

## 2. 查询性能优化

### 2.1 DSL 优化技巧

```json
// ❌ 慢查询：全表扫描 + 深度分页
{
  "query": { "match": { "message": "error" } },
  "from": 10000,
  "size": 10
}

// ✅ 优化：使用 search_after 分页
{
  "query": { "match": { "message": "error" } },
  "search_after": [1678901234000, "doc_id"],
  "size": 10,
  "sort": [{ "timestamp": { "order": "desc" } }, { "_id": { "order": "asc" } }]
}
```

---

## 3. 写入性能调优

```yaml
# 批量写入配置
POST _bulk
{ "index": { "_index": "logs", "_id": "1" } }
{ "timestamp": "2026-08-13T10:00:00", "level": "INFO" }

# 批量大小建议：1000-5000 条/批
# 刷新间隔调整为 30s-60s
# 使用 async translog
```

---

## 4. 运维监控

```yaml
# 关键监控指标
indices.segments.count          # 段数量
indices.query.cache.size        # 查询缓存
indices.fetch.total.time        # 取回耗时
indices.search.query_current    # 当前查询数
jvm.memory.used                 # JVM 内存
os.load_average                 # 系统负载
```

---

**参考**: Elasticsearch 官方文档、Elastic Stack 生产实践、CNCF 搜索最佳实践
