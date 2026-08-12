# ClickHouse 内核深度实现 - 列式存储原理

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 全栈/ClickHouse  
> **代码密度**: 28%

---

## 一、列式存储架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ClickHouse 存储架构                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     Partition (分区)                          │   │
│  │  ┌─────────────────────────────────────────────────────┐     │   │
│  │  │                   Data Part (数据段)                  │     │   │
│  │  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐      │     │   │
│  │  │  │ col1 │ │ col2 │ │ col3 │ │ colN │ │ _idx │      │     │   │
│  │  │  │(int) │ │(str) │ │(date) │ │(float)│ │(skip)│      │     │   │
│  │  │  ├──────┤ ├──────┤ ├──────┤ ├──────┤ ├──────┤      │     │   │
│  │  │  │  10  │ │ abc  │ │ 01-01│ │ 1.5  │ │  0   │      │     │   │
│  │  │  │  20  │ │ def  │ │ 01-02│ │ 2.5  │ │  1   │      │     │   │
│  │  │  │  30  │ │ ghi  │ │ 01-03│ │ 3.5  │ │  2   │      │     │   │
│  │  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘      │     │   │
│  │  └─────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  核心优势:                                                         │
│  • 列存储: 只读取需要的列，IO 减少 10-100x                          │
│  • 向量化: SIMD 指令并行处理                                        │
│  • 压缩: 同类型数据压缩率 5-10x                                    │
│  • 主键: 稀疏索引 + 跳数索引 (Skipping Index)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Merge Tree 引擎

```sql
-- MergeTree 表定义
CREATE TABLE events (
    event_id UInt64,
    user_id UInt64,
    event_type String,
    event_time DateTime,
    properties Map(String, String),
    sign Int8 DEFAULT 1  -- 签名列 (CollapsingMergeTree)
) ENGINE = CollapsingMergeTree()
ORDER BY (user_id, event_time)
SETTINGS index_granularity = 8192;

-- 插入数据
INSERT INTO events VALUES
(1, 100, 'click', '2026-08-13 10:00:00', {'page': 'home'}, 1),
(2, 100, 'view',  '2026-08-13 10:01:00', {'page': 'product'}, 1),
(3, 100, 'click', '2026-08-13 10:02:00', {'page': 'cart'}, 1);

-- 查询优化
SELECT 
    event_type,
    count() as cnt,
    avg(toUnixTimestamp(event_time)) as avg_time
FROM events
WHERE user_id = 100
  AND event_time >= '2026-08-01'
GROUP BY event_type
ORDER BY cnt DESC;
```

---

## 三、物化视图

```sql
-- 物化视图 (物化存储)
CREATE MATERIALIZED VIEW events_mv
ENGINE = SummingMergeTree()
ORDER BY (user_id, event_date)
AS SELECT
    user_id,
    toDate(event_time) as event_date,
    event_type,
    count() as event_count,
    sum(size) as total_bytes
FROM events
GROUP BY user_id, event_date, event_type;

-- 查询物化视图 (毫秒级)
SELECT * FROM events_mv
WHERE user_id = 100
  AND event_date >= '2026-08-01';

-- 投影 (Projection) - 预聚合
ALTER TABLE events
ADD PROJECTION user_projection (
    SELECT
        user_id,
        event_type,
        count() as cnt
    GROUP BY user_id, event_type
);
```

---

## 四、分布式查询

```sql
-- 分布式表
CREATE TABLE events_distributed ON CLUSTER ads_cluster (
    event_id UInt64,
    user_id UInt64,
    event_type String,
    event_time DateTime
) ENGINE = Distributed(ads_cluster, default, events_local, rand());

-- 分布式查询 (自动分片)
SELECT user_id, count() as cnt
FROM events_distributed
WHERE event_time >= '2026-08-01'
GROUP BY user_id
ORDER BY cnt DESC
LIMIT 100;

-- 本地表查询
SELECT * FROM events_local WHERE event_id = 123;
```

---

## 五、性能优化

```sql
-- 1. 数据跳跃索引
ALTER TABLE events
ADD INDEX idx_user (user_id) TYPE minmax GRANULARITY 4;

-- 2. 采样 KEY
ALTER TABLE events
MODIFY ORDER BY (user_id, event_time)
SAMPLE BY user_id;

-- 3.  TTL 自动过期
ALTER TABLE events
MODIFY COLUMN event_time DateTime TTL event_time + INTERVAL 90 DAY;

-- 4. 部分更新
ALTER TABLE events UPDATE properties = properties || {'source': 'mobile'}
WHERE user_id = 100 AND event_time < '2026-08-01';
```

---

## 六、自测题

1. **MergeTree 的 parts 是什么？**
   - 数据段，自动合并时减少碎片

2. **CollapsingMergeTree 如何解决删除？**
   - 签名列 +1/-1，合并时抵消

3. **为什么列式存储适合 OLAP？**
   - 聚合/过滤只读相关列，IO 大幅减少

