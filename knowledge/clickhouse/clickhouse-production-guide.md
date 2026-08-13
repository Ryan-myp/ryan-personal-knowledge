# ClickHouse 生产环境实战

> 深入 ClickHouse 架构、查询优化、运维实践。

---

## 1. 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                        ClickHouse                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Server 1 │  │ Server 2 │  │ Server 3 │  ...             │
│  │ (Replica)│  │ (Replica)│  │ (Replica)│                   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│       │             │             │                         │
│       └─────────────┴─────────────┘                         │
│                    │                                         │
│           ┌────────▼────────┐                                │
│           │   ZooKeeper     │  (分布式协调)                  │
│           │  (Metadata)     │                                │
│           └─────────────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 引擎选择

| 引擎 | 适用场景 | 特点 |
|------|----------|------|
| MergeTree | 核心表 | 支持分区、索引 |
| ReplicatedMergeTree | 分布式 | 数据副本 |
| Distributed | 查询分发 | 不存储数据 |
| Join | 大表关联 | 内存中的哈希连接 |
| AggregatingMergeTree | 预聚合 | 加速聚合查询 |

---

## 3. 查询优化

```sql
-- 使用 PREWHERE 代替 WHERE
SELECT * FROM events
PREWHERE event_time > '2024-01-01'
WHERE user_id = 12345;

-- 使用 ASSUME_COMPLETENESS
SELECT * FROM events
SETTINGS assume_completeness_of_parts = 1;

-- 并行读取
SET max_threads = 8;
```

---

## 4. 实践 Checklist
- [ ] 选择合适的分区键
- [ ] 启用压缩算法
- [ ] 定期 MERGE 优化
- [ ] 监控查询慢日志

**参考**: ClickHouse 官方文档、Yandex 生产实践
