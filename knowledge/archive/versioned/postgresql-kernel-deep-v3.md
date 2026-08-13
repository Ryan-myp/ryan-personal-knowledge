# PostgreSQL 内核深度解析

> 深入 PostgreSQL 核心：查询优化器、MVCC、WAL、索引结构。
> 源码级分析，包含生产环境优化。
> 适用对象：DBA、后端工程师、数据库工程师

---

## 1. 查询优化器

### 1.1 优化器架构

```
PostgreSQL 查询优化流程：

┌─────────────────────────────────────────────────────────────┐
│                  查询优化器架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Parse Tree（解析树）                                      │
│     └── SQL → 语法分析 → AST                                │
│                                                             │
│  2. Query Tree（查询树）                                      │
│     └── 语义分析 → 查询转换                                 │
│                                                             │
│  3. Plan Tree（计划树）                                       │
│     ├── 成本估算                                             │
│     ├── 查询重写                                            │
│     └── 规划算法                                             │
│                                                             │
│  4. Exec State（执行状态）                                    │
│     └── 计划执行 → 返回结果                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 执行计划类型

```
┌─────────────────────────────────────────────────────────────┐
│                  执行计划类型                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  顺序扫描 (Seq Scan)                                         │
│  ├── 全表扫描                                                │
│  └── 适用于小表或无索引场景                                  │
│                                                             │
│  索引扫描 (Index Scan)                                       │
│  ├── B-Tree 索引                                             │
│  ├── 按索引顺序读取                                          │
│  └── 适用于有索引的大表                                      │
│                                                             │
│  位图索引扫描 (Bitmap Index Scan)                            │
│  ├── 多个索引结果合并                                        │
│  └── 适用于多条件查询                                        │
│                                                             │
│  嵌套循环 (Nested Loop)                                      │
│  ├── 驱动表 + 被驱动表                                       │
│  └── 适用于小表关联                                          │
│                                                             │
│  哈希连接 (Hash Join)                                        │
│  ├── 构建哈希表                                              │
│  └── 适用于大表关联                                          │
│                                                             │
│  合并连接 (Merge Join)                                       │
│  ├── 有序合并                                                │
│  └── 适用于已排序数据                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. MVCC 实现

### 2.1 可见性规则

```
PostgreSQL MVCC 可见性规则：

1. 事务开始时的 Snapshot
   └── 快照包含已提交的事务 ID

2. 行版本可见性
   ├── xmin：行版本创建事务
   ├── xmax：行版本删除事务
   ├── 当前事务可见当且仅当：
   │   ├── 行版本 xmin <= 当前事务 ID
   │   └── 行版本 xmax 未设置或 xmax > 当前事务 ID
   └── 其他事务可见性取决于快照

3. Heap Tuple 结构
   ├── t_xmin：创建事务
   ├── t_xmax：删除事务
   ├── t_ctid：下一个版本指针
   └── t_infomask：可见性标志
```

### 2.2 Vacuum 机制

```
Vacuum 工作原理：

1. 回收 dead tuple
   └── 标记可回收的行

2. 更新 visibility map
   └── 标记全可见页

3. 回收空闲空间
   └── 返回给表空间

自动 Vacuum：
├── autovacuum_enabled
├── autovacuum_vacuum_threshold
├── autovacuum_vacuum_scale_factor
└── autovacuum_analyze_threshold
```

---

## 3. WAL 日志

### 3.1 WAL 结构

```
WAL (Write-Ahead Log) 结构：

┌─────────────────────────────────────────────────────────────┐
│                    WAL Record                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Record Header                                               │
│  ├── 总长度                                                  │
│  ├── 操作类型                                                │
│  └── 后续 Record 指针                                        │
│                                                             │
│  Block Reference（可选）                                     │
│  ├── 数据页 ID                                               │
│  └── 页内偏移                                                │
│                                                             │
│  Data（数据）                                                │
│  └── 实际操作数据                                            │
│                                                             │
│  CRC Checksum                                                │
│  └── 数据完整性校验                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 故障恢复

```
WAL 故障恢复流程：

1. 崩溃时
   └── 未提交的事务未写入数据文件

2. 重启恢复
   ├── 重放 WAL 记录
   ├── 提交已记录的事务
   └── 回滚未提交的事务

3. 快速恢复
   ├── 只重放需要的 Record
   ├── 使用 Checkpoint 加速
   └── Parallel Recovery 加速
```

---

## 4. 索引结构

### 4.1 B-Tree 索引

```
B-Tree 索引结构：

┌─────────────────────────────────────────────────────────────┐
│                    B-Tree 结构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Root Page（根页面）                                         │
│  ├── 指向子页面的指针                                        │
│  └── 分隔值                                                  │
│        │                                                      │
│       /|\                                                     │
│      / | \                                                    │
│  Leaf Pages（叶子页面）                                       │
│  ├── 实际数据指针                                            │
│  ├── 有序排列                                                │
│  └── 页内指针（双向链表）                                     │
│                                                             │
│  特点：                                                      │
│  ├── 平衡二叉树                                              │
│  ├── O(log n) 查询复杂度                                     │
│  └── 适合范围查询                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 GiST 索引

```
GiST (Generalized Search Tree) 索引：

适用场景：
├── 全文搜索
├── 几何数据
├── 范围类型
└── 自定义操作符

特点：
├── 灵活的数据结构
├── 支持自定义操作
└── 适合复杂查询
```

---

## 5. 性能优化

### 5.1 配置优化

```postgresql
-- 内存配置
shared_buffers = 4GB                    # 共享内存缓冲区
work_mem = 64MB                        # 查询工作内存
maintenance_work_mem = 512MB           # 维护操作内存

-- WAL 配置
wal_buffers = 64MB                     # WAL 缓冲区
max_wal_size = 4GB                     # 最大 WAL 大小
min_wal_size = 1GB                     # 最小 WAL 大小

-- 查询优化
effective_cache_size = 12GB            # 有效缓存大小
random_page_cost = 1.1                 # 随机页成本
effective_io_concurrency = 200         # IO 并发数

-- Vacuum 配置
autovacuum_vacuum_scale_factor = 0.05  # Vacuum 触发阈值
autovacuum_analyze_scale_factor = 0.02 # Analyze 触发阈值
```

### 5.2 查询优化

```sql
-- 使用 EXPLAIN 分析查询
EXPLAIN (ANALYZE, BUFFERS, TIMING) 
SELECT * FROM orders WHERE user_id = 100;

-- 创建合适的索引
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_create_time ON orders(create_time DESC);

-- 分析表统计信息
ANALYZE orders;
```

---

## 6. 监控诊断

### 6.1 关键指标

```sql
-- 连接数监控
SELECT count(*) FROM pg_stat_activity;

-- 慢查询监控
SELECT query, calls, total_exec_time 
FROM pg_stat_statements 
ORDER BY total_exec_time DESC 
LIMIT 10;

-- 表大小监控
SELECT 
    schemaname,
    relname,
    pg_size_pretty(pg_total_relation_size(relid)) AS size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- 死元组监控
SELECT 
    schemaname,
    relname,
    n_dead_tup,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

### 6.2 故障排查

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 连接数满 | 无法连接 | `SHOW max_connections` | 增加连接数/优化连接池 |
| 慢查询 | 响应慢 | `pg_stat_statements` | 优化索引/查询 |
| 锁等待 | 阻塞 | `pg_locks` | 杀死阻塞会话 |
| WAL 堆积 | 磁盘满 | `pg_wal` | 调整 wal_level |

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 查询优化 | Cost-based 优化 |
| MVCC | Snapshot + Tuple 版本 |
| WAL | 预写日志 + 恢复 |
| 索引 | B-Tree/GiST/Hash |

### 7.2 最佳实践

- [ ] 合理配置内存参数
- [ ] 定期 Vacuum 维护
- [ ] 监控慢查询
- [ ] 使用 EXPLAIN 分析
- [ ] 建立监控告警

---

*最后更新：2026-08-11*
*作者：Ryan*
