# ClickHouse 内核深度解析

> 深入 ClickHouse 核心：存储引擎、查询执行、MergeTree、分布式架构。
> 源码级分析，包含性能优化和故障排查。
> 适用对象：数据工程师、DBA、后端工程师

---

## 1. MergeTree 引擎

### 1.1 数据结构

```
┌─────────────────────────────────────────────────────────────┐
│                  MergeTree 数据结构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Part (数据部分)                                             │
│  ├── 0000000_0000000_0         # 主数据文件                   │
│  ├── 0000000_0000000_0.bin     # 二进制数据                   │
│  ├── 0000000_0000000_0.idx     # 索引文件                     │
│  └── 0000000_0000000_0.crc     # 校验和                       │
│                                                             │
│  Primary Key (主键)                                          │
│  ├── 稀疏索引，存储 min/max 值                              │
│  ├── 不包含所有数据行                                        │
│  └── 用于跳过不匹配的数据块                                  │
│                                                             │
│  Secondary Index (二级索引)                                  │
│  ├── mark 文件，每 N 行一个索引点                            │
│  └── 支持跳跃扫描                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 数据写入流程

```
写入流程：

1. INSERT 请求到达
2. 数据写入 INSERT缓冲
3. 异步合并到 Part
4. 后台线程执行 Merge

关键参数：
- insert_quiescent_timeout: 插入静默超时
- min_insert_block_size_rows: 最小插入块行数
- min_insert_block_size_bytes: 最小插入块字节数
```

### 1.3 Go 实现模拟

```go
// mergetree.go (简化)

package clickhouse

type MergeTree struct {
    parts      []*Part
    mergeQueue chan *MergeTask
}

type Part struct {
    name      string
    rows      int64
    minKey    []byte
    maxKey    []byte
    data      []byte
}

func (mt *MergeTree) Insert(rows [][]byte) {
    part := &Part{
        rows: int64(len(rows)),
        data: rows,
    }
    mt.parts = append(mt.parts, part)
    
    // 异步合并
    select {
    case mt.mergeQueue <- &MergeTask{parts: []*Part{part}}:
    default:
    }
}

func (mt *MergeTree) merge() {
    // 合并逻辑
}
```

---

## 2. 查询执行

### 2.1 查询管道

```
┌─────────────────────────────────────────────────────────────┐
│                    查询执行管道                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  读取器 (Readers)                                            │
│  ├── 从磁盘读取数据块                                        │
│  └── 并行读取多个 Part                                       │
│                                                             │
│  处理器 (Processors)                                         │
│  ├── Filter: 过滤数据                                        │
│  ├── Aggregator: 聚合计算                                    │
│  ├── Sorter: 排序                                            │
│  └── Join: 连接                                              │
│                                                             │
│  写入器 (Writers)                                            │
│  ├── 将结果发送给客户端                                       │
│  └── 或写入临时文件                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 并行执行

```
并行执行策略：

1. 分片并行
   - 数据分片到多个服务器
   - 每个服务器并行执行

2. 线程并行
   - 多个线程处理不同数据块
   - 共享内存池

3. SIMD 优化
   - 使用向量化指令
   - 单次处理多行数据
```

### 2.3 Go 实现

```go
// parallel_query.go

package clickhouse

import (
    "sync"
)

type QueryPipeline struct {
    readers  []Reader
    processors []Processor
    writers  []Writer
}

type Reader interface {
    Next() ([]Row, error)
    Close() error
}

type Processor interface {
    Process(input <-chan []Row, output chan<- []Row)
}

func (p *QueryPipeline) Execute() {
    var wg sync.WaitGroup
    
    // 启动读取器
    for i := range p.readers {
        wg.Add(1)
        go func(r Reader) {
            defer wg.Done()
            r.Next()
        }(p.readers[i])
    }
    
    // 启动处理器
    for i := range p.processors {
        wg.Add(1)
        go func(proc Processor) {
            defer wg.Done()
            proc.Process(input, output)
        }(p.processors[i])
    }
    
    wg.Wait()
}
```

---

## 3. 分布式架构

### 3.1 集群部署

```
分布式集群架构：

┌─────────────────────────────────────────────────────────────┐
│                      Client                                  │
│                              │                               │
│                   ┌──────────┴──────────┐                   │
│                   │                     │                     │
│              ┌────▼────┐          ┌────▼────┐              │
│              │SHARD 1 │          │SHARD 2 │              │
│              │  ┌───┐  │          │  ┌───┐  │              │
│              │  │N1 │  │◄────────►│  │N1 │  │              │
│              │  └───┘  │          │  └───┘  │              │
│              │  ┌───┐  │          │  ┌───┐  │              │
│              │  │N2 │  │          │  │N2 │  │              │
│              │  └───┘  │          │  └───┘  │              │
│              └─────────┘          └─────────┘              │
└─────────────────────────────────────────────────────────────┘

特点：
- 每个 Shard 独立存储部分数据
- 查询分发到所有 Shard
- 结果汇聚返回客户端
```

### 3.2 数据分片

```
分片策略：

1. 哈希分片
   - 按主键哈希分发
   - 数据分布均匀

2. 范围分片
   - 按时间范围
   - 便于范围查询

3. 随机分片
   - 随机分配
   - 负载均衡
```

---

## 4. 性能优化

### 4.1 索引优化

```sql
-- 选择合适的采样函数
CREATE TABLE orders (
    id UInt64,
    create_time DateTime,
    amount Decimal(10,2),
    INDEX idx_time create_time TYPE minmax GRANULARITY 4096
) ENGINE = MergeTree()
ORDER BY (id, create_time);

-- 使用物化视图加速聚合
CREATE MATERIALIZED VIEW orders_mv
ENGINE = SummingMergeTree()
ORDER BY (date, product_id)
AS SELECT
    toDate(create_time) AS date,
    product_id,
    sum(amount) AS total
FROM orders
GROUP BY date, product_id;
```

### 4.2 查询优化

```sql
-- 使用 FINAL 修正数据
SELECT * FROM orders FINAL;

-- 分批查询大数据
SELECT * FROM orders WHERE create_time >= '2024-01-01'
SETTINGS max_partitions_per_insert_block = 100;

-- 使用预热加速查询
SYSTEM PREHOT CACHE /var/lib/clickhouse/cache;
```

---

## 5. 监控与故障排查

### 5.1 监控指标

```sql
-- 查看系统表
SELECT * FROM system.merges;
SELECT * FROM system.replicas;
SELECT * FROM system.parts;

-- 查看慢查询
SELECT * FROM system.query_log
WHERE type = 'query_finish'
AND query_duration_ms > 1000
ORDER BY event_time;
```

### 5.2 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 合并慢 | CPU 高 | `system.merges` | 调整合并线程数 |
| 查询慢 | 延迟高 | `system.query_log` | 优化索引 |
| 磁盘满 | 写入失败 | `system.disks` | 清理旧数据 |
| 复制延迟 | 数据不一致 | `system.replicas` | 检查网络 |

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 存储 | MergeTree + 稀疏索引 |
| 查询 | 并行管道执行 |
| 分布式 | Shard + Replica |
| 优化 | 物化视图 + 采样 |

### 6.2 最佳实践

- [ ] 选择合适的引擎
- [ ] 优化索引设计
- [ ] 监控合并进度
- [ ] 定期清理数据
- [ ] 合理设置参数

---

*最后更新：2026-08-11*
*作者：Ryan*
