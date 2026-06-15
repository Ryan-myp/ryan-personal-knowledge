# ClickHouse 内核深度：MergeTree 引擎源码级解析

> 逐行解析 MergeTree 存储格式 + 物化视图原理 + 数据压缩 + 查询优化器 + 生产排障

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 ClickHouse

想象一个图书馆的书架：

```
传统数据库（MySQL）= 抽屉式书架
  → 每个抽屉放一条记录
  → 查找特定记录快，但统计所有书很慢

ClickHouse = 层叠式书架
  → 每层放同一种类的书（列式存储）
  → 统计时只看需要的层，不用翻所有抽屉
  → 压缩率高（同类书放在一起，压缩效果好）
```

### 为什么广告平台用 ClickHouse？

| 场景 | MySQL | ClickHouse |
|------|-------|-----------|
| 实时竞价 | ✅ 快 | ❌ 太重 |
| 用户画像查询 | ✅ | ✅ |
| **广告日志分析** | ❌ 太慢 | ✅ **秒级** |
| **实时报表** | ❌ 跑不完 | ✅ **1 秒出结果** |
| **数据聚合** | ❌ | ✅ **向量化执行** |

**核心指标：**
- 每日广告曝光日志：10-50 亿条
- 需要支持的查询：PV/UV/CTR/CVR/eCPM
- SLA：查询响应 < 3 秒

---

## 第二部分：MergeTree 存储格式（逐行解析）

### 2.1 数据在磁盘上怎么存？

```
Table: ad_events
├── data/
│   ├── 20240101_1_1_0/          # 分区 20240101，Part 1-1-0
│   │   ├── ad_event_id.bin      # 列：广告事件 ID
│   │   ├── user_id.bin          # 列：用户 ID
│   │   ├── campaign_id.bin      # 列：广告活动 ID
│   │   ├── timestamp.bin        # 列：时间戳
│   │   ├── event_type.bin       # 列：事件类型
│   │   ├── cost.bin             # 列：花费
│   │   └── marks.mrk2           # 标记文件（稀疏索引）
│   ├── 20240101_2_2_0/          # 另一个 Part
│   └── ...
├── indexes/                       # 全局索引
├── primary.idx                    # 主键索引
└── parts.txt                      # 当前活跃的 Parts 列表
```

### 2.2 Part 的内部结构

```
一个 Part = 一组列文件 + 标记文件 + 索引文件

列文件 (.bin):
┌──────────────────────────────────────────┐
│ Block 1 (10000 行)                       │
│ ├─ ad_event_id: [1, 2, 3, ..., 10000]   │
│ ├─ user_id:    [101, 102, 103, ..., 200]│
│ ├─ timestamp:  [1704067200, ..., 1704070799]│
│ └─ cost:       [0.5, 1.2, 0.8, ..., 3.5]│
│                                          │
│ Block 2 (10000 行)                       │
│ ...                                    │
└──────────────────────────────────────────┘

标记文件 (.mrk2):
┌──────────────────────────────────────────┐
│ Block 1: offset=0, rows=10000            │
│ Block 2: offset=10000, rows=10000        │
│ Block 3: offset=20000, rows=10000        │
│ ...                                      │
│ Block N: offset=(N-1)*10000, rows=10000  │
└──────────────────────────────────────────┘

关键：标记文件是稀疏索引！
- 不是每行都有索引
- 每 8192 行有一个标记（default_index_granularity）
- 查询时先查标记文件定位 Block，再在 Block 内二分查找
```

### 2.3 Go 模拟 MergeTree 存储

```go
package clickhouse

import (
    "fmt"
    "os"
    "sort"
)

// MergeTreePart 一个数据 Part
type MergeTreePart struct {
    MinDate     string  // 最小日期
    MaxDate     string  // 最大日期
    MinTimeStamp uint64 // 最小时间戳
    MaxTimeStamp uint64 // 最大时间戳
    PrimaryKey  string  // 主键值范围
    Rows        uint64  // 行数
    BytesOnDisk uint64  // 磁盘大小
}

// 排序规则：按主键排序
// 主键通常是：date, event_type, user_id
// 排序的好处：
// 1. 相同值的行放在一起，压缩效果好
// 2. 范围查询时可以跳过不相关的 Part
// 3. 稀疏索引更高效

// 列文件格式
type ColumnBlock struct {
    ColumnName string
    Data       []byte
    Rows       uint32
    MinVal     interface{}
    MaxVal     interface{}
}

// 写入列数据（压缩前）
func (cb *ColumnBlock) WriteToFile(path string) error {
    f, err := os.Create(path)
    if err != nil {
        return err
    }
    defer f.Close()
    
    // 写入列头
    fmt.Fprintf(f, "%s\n", cb.ColumnName)
    fmt.Fprintf(f, "%d\n", cb.Rows)
    
    // 写入数据（未压缩）
    _, err = f.Write(cb.Data)
    return err
}

// 写入标记文件（稀疏索引）
// 每 8192 行一个标记
func WriteMarkFile(path string, blockSize uint64) error {
    f, err := os.Create(path)
    if err != nil {
        return err
    }
    defer f.Close()
    
    // 计算有多少个 Block
    numBlocks := blockSize / 8192
    if blockSize%8192 != 0 {
        numBlocks++
    }
    
    for i := uint64(0); i < numBlocks; i++ {
        // 每个标记包含：偏移量和行数
        fmt.Fprintf(f, "%d\t%d\n", i*8192, 8192)
    }
    
    return nil
}
```

### 2.4 数据压缩

```
ClickHouse 使用多种压缩算法：

1. LZ4: 速度快，压缩率一般（推荐默认）
2. ZSTD: 压缩率高，速度慢（适合冷数据）
3. Delta + DoubleDelta: 对递增数字特别好
4. Gorilla: 对浮点数特别好

压缩效果对比：

原始数据: 100GB
LZ4:      20-30GB (压缩率 3-5x)
ZSTD:     10-15GB (压缩率 7-10x)

广告日志压缩效果特别好，因为：
- 同一天的数据放在一起 → 日期列高度重复
- 同一 campaign 的曝光放在一起 → campaign_id 高度重复
- 花费是浮点数 → Gorilla 压缩效果极好
```

```go
// 压缩算法选择策略
func ChooseCompressionAlgorithm(columnType string, data []byte) string {
    switch columnType {
    case "UInt64", "Int64":
        // 递增数字用 Delta 压缩
        if isIncreasing(data) {
            return "DoubleDelta"
        }
        return "LZ4"
    case "Float64":
        // 浮点数用 Gorilla 压缩
        return "Gorilla"
    case "String":
        // 字符串用 LZ4
        return "LZ4"
    default:
        return "LZ4"
    }
}

// isIncreasing 检查数据是否递增
func isIncreasing(data []byte) bool {
    // 解析为整数，检查是否递增
    // 简化实现
    return true
}
```

---

## 第三部分：物化视图深度

### 3.1 物化视图是什么？

```
普通视图 = SQL 别名，查询时实时计算
物化视图 = 预先计算好结果，存在磁盘上

CREATE MATERIALIZED VIEW ad_daily_summary
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, campaign_id)
AS SELECT
    toDate(event_time) AS event_date,
    campaign_id,
    count() AS impressions,
    sum(cost) AS total_cost,
    uniq(user_id) AS uv
FROM ad_events
GROUP BY event_date, campaign_id;

查询物化视图：
SELECT event_date, campaign_id, impressions, total_cost
FROM ad_daily_summary
WHERE event_date >= '2024-01-01';

→ 直接查预计算的结果，不用扫描几十亿行原始数据！
```

### 3.2 SummingMergeTree

```
SummingMergeTree 自动对指定列求和

数据写入：
┌─────────────────────────────────────────────────────┐
│ event_date  │ campaign_id │ impressions │ cost      │
├─────────────────────────────────────────────────────┤
│ 2024-01-01  │ C001        │ 100         │ 50.0      │
│ 2024-01-01  │ C001        │ 200         │ 100.0     │
│ 2024-01-01  │ C002        │ 150         │ 75.0      │
└─────────────────────────────────────────────────────┘

后台合并时自动求和：
┌─────────────────────────────────────────────────────┐
│ event_date  │ campaign_id │ impressions │ cost      │
├─────────────────────────────────────────────────────┤
│ 2024-01-01  │ C001        │ 300         │ 150.0     │  ← 100+200
│ 2024-01-01  │ C002        │ 150         │ 75.0      │
└─────────────────────────────────────────────────────┘
```

```go
// SummingMergeTree 合并逻辑
type SummingMergeTree struct {
    data map[string]map[string]int64 // date → campaign → impressions
    costs map[string]map[string]float64 // date → campaign → cost
}

func (smt *SummingMergeTree) Merge(parts []Part) {
    for _, part := range parts {
        for _, row := range part.Rows {
            key := fmt.Sprintf("%s|%s", row.Date, row.CampaignID)
            smt.data[key] += row.Impressions
            smt.costs[key] += row.Cost
        }
    }
}
```

### 3.3 物化视图的两种模式

| 模式 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| **POPULATE** | 创建时填充历史数据 | 立即可用 | 创建慢 |
| **不 POPULATE** | 只存新数据 | 创建快 | 需要手动填充历史 |

```sql
-- 推荐做法：不 POPULATE，手动填充
CREATE MATERIALIZED VIEW ad_daily_summary
ENGINE = SummingMergeTree()
ORDER BY (event_date, campaign_id)
AS SELECT ... FROM ad_events;

-- 手动填充历史数据
INSERT INTO ad_daily_summary
SELECT toDate(event_time) AS event_date, campaign_id, ...
FROM ad_events
WHERE event_time < now() - INTERVAL 1 DAY;
```

---

## 第四部分：查询优化器

### 4.1 谓词下推（Predicate Pushdown）

```
查询：
SELECT campaign_id, count()
FROM ad_events
WHERE event_date >= '2024-01-01'
  AND event_date < '2024-02-01'
  AND user_id IN (1, 2, 3)

优化前：
1. 扫描所有 Part（包括 2023 年的）
2. 过滤 event_date
3. 过滤 user_id
4. 聚合

优化后（谓词下推）：
1. 先查稀疏索引，跳过不相关的 Part（2023 年的 Part 直接跳过）
2. 只扫描 2024-01 的 Part
3. 过滤 user_id
4. 聚合

性能提升：10x - 100x
```

### 4.2 向量化执行

```
传统行式处理：
FOR EACH row:
    IF row.user_id IN (1,2,3) THEN
        count++
    END IF
END FOR

ClickHouse 向量化处理：
FOR EACH block (8192 rows):
    mask = (user_id == 1 OR user_id == 2 OR user_id == 3)
    count += popcount(mask)
END FOR

向量化优势：
1. 一次处理 8192 行，减少循环开销
2. SIMD 指令并行处理
3. 更好的 CPU 缓存命中率
```

### 4.3 索引跳跃过滤（Skipping Indexes）

```
主键索引只能用于等值和范围查询

如果需要查询 user_id = 123，但主键是 (date, campaign_id)？

解决方案：使用数据跳过索引（Data Skipping Indexes）

CREATE TABLE ad_events (
    event_date Date,
    campaign_id UInt32,
    user_id UInt64,
    cost Float64,
    INDEX idx_user_id user_id TYPE tokenbf_v1(30000, 2, 0) GRANULARITY 4
) ENGINE = MergeTree()
ORDER BY (event_date, campaign_id);

查询时：
1. 先查 tokenbf_v1 索引，快速判断 user_id=123 是否存在
2. 如果不存在，跳过整个 Part
3. 如果可能存在，再扫描数据

性能提升：10x - 100x
```

---

## 第五部分：后台合并机制

### 5.1 Merge 过程

```
MergeTree 后台自动合并 Part

触发条件：
1. Part 数量超过 merge_tree.max_parts_to_total (默认 100)
2. Part 大小超过 merge_tree.total_size_max (默认 100GB)
3. 定时任务（每 10 秒检查一次）

合并过程：
1. 选择要合并的 Part（通常是相邻的）
2. 读取所有 Part 的数据
3. 按主键排序
4. 压缩并写入新 Part
5. 替换旧 Part

注意：合并是后台进行的，不影响查询
```

```go
type MergeScheduler struct {
    parts []Part
    maxParts int
    totalSizeMax int64
}

func (ms *MergeScheduler) ShouldMerge() bool {
    if len(ms.parts) > ms.maxParts {
        return true
    }
    
    totalSize := int64(0)
    for _, p := range ms.parts {
        totalSize += p.Size
    }
    
    return totalSize > ms.totalSizeMax
}

func (ms *MergeScheduler) Merge() error {
    // 1. 选择要合并的 Part
    selected := ms.selectPartsToMerge()
    
    // 2. 读取数据
    rows := make([]Row, 0)
    for _, part := range selected {
        rows = append(rows, part.ReadAllRows()...)
    }
    
    // 3. 按主键排序
    sort.Slice(rows, func(i, j int) bool {
        return rows[i].PrimaryKey < rows[j].PrimaryKey
    })
    
    // 4. 压缩并写入新 Part
    newPart := ms.compressAndWrite(rows)
    
    // 5. 替换旧 Part
    ms.replaceParts(selected, newPart)
    
    return nil
}
```

### 5.2 合并对查询的影响

```
合并期间会发生什么？

1. 读取侧：继续查询旧的 Part（不影响查询）
2. 写入侧：继续写入新的 Part（不影响写入）
3. 合并完成后：旧的 Part 被删除，新的 Part 生效

关键：合并是异步的，不会阻塞查询和写入！
```

---

## 第六部分：生产排障案例

### 6.1 查询慢

```
现象：广告报表查询从 1 秒变成 30 秒

排查步骤：
1. EXPLAIN 查看执行计划
2. 检查是否走了稀疏索引
3. 检查 Part 数量是否太多
4. 检查是否有全表扫描

解决方案：
1. 添加合适的 ORDER BY
2. 使用物化视图预计算
3. 调整 merge_tree 参数
4. 使用数据跳过索引
```

```sql
-- 查看执行计划
EXPLAIN PIPELINE
SELECT campaign_id, count()
FROM ad_events
WHERE event_date >= '2024-01-01'
GROUP BY campaign_id;

-- 查看 Part 信息
SELECT
    name,
    parts,
    bytes_on_disk
FROM system.parts
WHERE table = 'ad_events';
```

### 6.2 内存溢出

```
现象：ClickHouse 查询 OOM

原因：
1. 查询返回太多数据（没有 LIMIT）
2. GROUP BY 产生太多分组
3. JOIN 操作内存不足

解决方案：
1. 添加 LIMIT
2. 使用 GROUP BY WITH TOTALS
3. 增大 max_memory_usage
4. 使用 merge_tree 的 max_bytes_before_external_group_by
```

```sql
-- 查看内存使用情况
SELECT
    query_id,
    memory_usage,
    peak_memory_usage
FROM system.processes;

-- 调整参数
SET max_memory_usage = 10000000000;  -- 10GB
SET max_bytes_before_external_group_by = 5000000000;  -- 5GB
```

### 6.3 数据不一致

```
现象：物化视图数据不对

原因：
1. 物化视图没有正确填充
2. 后台合并导致数据重复
3. 写入时使用了 INSERT SELECT 而不是 INSERT INTO ... SELECT

解决方案：
1. 手动填充物化视图
2. 检查写入方式
3. 使用 REPLACING MERGETREE 去重
```

---

## 第七部分：自测题

### 问题 1
ClickHouse 为什么比 MySQL 适合日志分析？

<details>
<summary>查看答案</summary>

1. **列式存储**：只读取需要的列
2. **向量化执行**：SIMD 批量处理
3. **高压缩率**：同类数据放在一起
4. **物化视图**：预计算聚合结果
5. **稀疏索引**：快速跳过不相关数据

</details>

### 问题 2
MergeTree 合并 Part 会影响查询吗？

<details>
<summary>查看答案</summary>

1. **不会**：合并是后台异步进行的
2. **读取**：继续查询旧的 Part
3. **写入**：继续写入新的 Part
4. **合并后**：旧的 Part 被删除
5. **性能**：合并期间查询可能稍慢（磁盘 IO）

</details>

### 问题 3
如何优化 ClickHouse 查询性能？

<details>
<summary>查看答案</summary>

1. **选择合适的 ORDER BY**：主键决定数据分布
2. **使用物化视图**：预计算聚合
3. **添加数据跳过索引**：加速过滤
4. **合理设置 PARTITION BY**：减少扫描
5. **使用 LIMIT**：限制返回行数

</details>

---

*本文档基于 ClickHouse 源码和生产实战整理。*