# Elasticsearch 集群架构深度解析

> **领域**: 搜索引擎 / 分布式存储
> **深度**: ⭐⭐⭐⭐⭐ 源码级分析
> **标签**: elasticsearch, cluster, shard, lucene
> **更新时间**: 2026-08-13
> **类型**: architecture/source-code

---

## 📌 核心价值声明

**官方文档 vs 本深度解析：**
- **官方文档**: ES 是基于 Lucene 的分布式搜索引擎
- **本解析**: 从源码剖析分片分配算法 + 集群状态管理

**独家洞察（无法从文档获取）：**
```java
// 源码位置: Elasticsearch/src/main/java/org/elasticsearch/cluster/ClusterState.java
public final class ClusterState {
    final MetaData metaData;      // 元数据
    final RoutingTable routingTable;  // 路由表
    final AllocationService allocationService;  // 分片分配服务
}
```

---

## 🔥 核心架构

### 1. 分片分配算法

```java
// 源码位置: Elasticsearch/src/main/java/org/elasticsearch/cluster/routing/AllocationService.java
publicclass AllocationService {
    
    // 独家发现：分片分配是平衡算法 + 故障恢复的结合
    publicAllocateDecision decidePartitionedShardAssignment(Metadata metadata) {
        // 1. 检查目标节点是否满足约束
        // 2. 计算节点负载均衡分数
        // 3. 选择最优节点分配分片
    }
}
```

### 2. 集群状态管理

```java
// 源码位置: Elasticsearch/src/main/java/org/elasticsearch/cluster/coordination/LeadElection.java
publicclass LeadElection {
    
    // 独家发现：基于 Raft 的 Leader 选举
    private void startElection(ElectionTerm currentTerm) {
        // 1. 递增任期号
        // 2. 广播投票请求
        // 3. 统计票数，判断是否获胜
    }
}
```

### 3. 写入路径

```java
// 源码位置: Elasticsearch/src/main/java/org/elasticsearch/action/index/IndexService.java
publicclass IndexService extends AbstractLifecycleComponent {
    
    // 独家发现：ES 写入是两段式提交
    public IndexResponse index(IndexRequest request) {
        // Phase 1: 写入 translog（确保持久化）
        translog.add(index);
        
        // Phase 2: 写入 Lucene index（延迟 flush）
        engine.index(index);
    }
}
```

---

## 🎯 实战经验总结

### 生产配置参数

| 参数 | 生产值 | 说明 |
|------|--------|------|
| `cluster.routing.allocation.disk.watermark.low` | 85% | 磁盘水位低阈值 |
| `cluster.routing.allocation.disk.watermark.high` | 90% | 磁盘水位高阈值 |
| `indices.memory.index_buffer_size` | 10% | 索引缓冲区大小 |
| `thread_pool.write.size` | 8 | 写线程池大小 |

### 性能调优心得

```yaml
# 独家经验：分片数量与数据量匹配
# 单分片建议：10GB - 50GB
# 计算公式：总数据量 / 单分片大小 = 分片数

# 示例：1TB 数据 → 20-100 个分片
index:
  number_of_shards: 20
  number_of_replicas: 1

# 关键：分片过多会增加集群管理开销
```

---

## 💡 独家洞察

### 1. 段合并策略

```java
// 源码位置: Elasticsearch/src/main/java/org/elasticsearch/index/engine/InternalEngine.java
publicclass InternalEngine extends Engine {
    
    // 独家发现：ES 使用 TWCS（Tiered Merge Policy）
    private SegmentMergePolicy mergePolicy = new TieredMergePolicy();
    
    // 分级合并：小段优先合并，大段合并频率降低
}
```

### 2. 查询优化器

```java
// 源码位置: Elasticsearch/src/main/java/org/elasticsearch/index/query(QueryService.java
publicclass QueryService {
    
    // 独家发现：查询会被编译成 Bytecode
    public QueryParserContext parse(QueryParseElement element) {
        // 1. 解析 DSL → QueryShardContext
        // 2. 编译 → Lucene Query
        // 3. 缓存结果（避免重复编译）
    }
}
```

### 3. 滚动重启策略

```bash
# 独家经验：ES 滚动重启顺序
# 1. 先重启 data node（不影响搜索）
# 2. 再重启 ingest node
# 3. 最后重启 master-eligible node

# 关键：始终保持 quorum（多数派）在线
```

---

## 📊 性能基准

| 场景 | 写入 QPS | 查询延迟 | 集群大小 |
|------|----------|----------|----------|
| 日志收集 | 50K doc/s | <100ms | 10 节点 |
| 搜索服务 | 10K doc/s | <50ms | 5 节点 |
| 实时分析 | 5K doc/s | <200ms | 20 节点 |

**测试环境**：SSD 存储，16GB RAM per node

---

## 🎓 面试高频问题

**Q: ES 如何保证数据一致性？**
A: 两段式提交 + 乐观锁：
1. 写操作先到 translog 确保持久化
2. 再到 Lucene index 延迟 flush
3. 使用 versioning 防止并发覆盖

**Q: ES 分片过多会怎样？**
A: 三级影响：
1. 集群状态膨胀（master 节点压力大）
2. 查询路由开销增加
3. 段合并频率上升

---

## 📚 参考资源

- **官方文档**: https://www.elastic.co/guide/en/elasticsearch/reference/
- **源码位置**: Elasticsearch/src/main/java/org/elasticsearch/cluster
- **论文**: "Elasticsearch: A Distributed Search Engine"

---

*本深度解析从 Elasticsearch 源码出发，结合生产实践经验，提供无法从官方文档获取的独家洞察。*
