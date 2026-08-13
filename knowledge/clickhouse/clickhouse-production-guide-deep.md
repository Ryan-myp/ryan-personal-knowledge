# ClickHouse 生产环境实战指南

> 深入 ClickHouse 生产部署：表引擎选择、分布式查询、数据压缩、性能调优。

---

## 1. 表引擎选择

```sql
-- MergeTree 系列 (推荐)
CREATE TABLE events (
    event_id UInt64,
    event_time DateTime,
    user_id UInt64,
    event_type String,
    properties Map(String, String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (user_id, event_time)
TTL event_time + INTERVAL 90 DAY TO DISK 'slow_storage';

-- ReplicatedMergeTree (集群)
CREATE TABLE events_replica (
    event_id UInt64,
    event_time DateTime
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
ORDER BY (event_id);

-- Distributed (分布式查询)
CREATE TABLE events_dist AS events ENGINE = Distributed('cluster_name', default, events, rand());
```

---

## 2. 数据写入优化

```sql
-- 批量插入 (推荐 1000-10000 条/批)
INSERT INTO events SELECT * FROM input WHERE ...;

-- 异步插入
SET async_insert = 1;
SET data_dogmatic = 1;

-- 合并配置
SET max_insert_block_size = 100000;
SET max_threads = 8;
```

---

## 3. 查询优化

```sql
-- 使用 PREWHERE 替代 WHERE
SELECT user_id, count() 
FROM events 
PREWHERE event_time >= '2026-01-01'
WHERE event_type = 'purchase'
GROUP BY user_id;

-- 使用物化视图
CREATE MATERIALIZED VIEW events_mv
TO events_agg AS
SELECT 
    user_id,
    toDate(event_time) as date,
    count() as pv,
    sum(amount) as revenue
FROM events
GROUP BY user_id, date;
```

---

## 4. 监控指标

```sql
SELECT 
    name,
    value
FROM system.metrics
WHERE metric IN (
    'ReadBytes', 'WrittenBytes', 
    'QueryTime', 'SelectedBytes',
    'BackgroundPoolTask', 'BackgroundMergesMutationsCount'
);
```

---

## 5. 实践 Checklist
- [ ] 合理选择表引擎
- [ ] 批量写入数据
- [ ] 使用物化视图预聚合
- [ ] 监控后台合并任务
- [ ] 定期清理过期数据
- [ ] 配置副本和分片

**参考**: ClickHouse 官方文档、Yandex 数据平台最佳实践
