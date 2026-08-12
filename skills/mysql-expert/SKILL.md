---
name: mysql-expert
description: "MySQL 专家技能 — InnoDB 内核、事务、锁机制、执行计划、调优实战"
version: 1.0.0
author: ryan
tags: [mysql, innodb, transaction, locking, performance, expert]
---

# MySQL 专家技能

> 从 InnoDB 源码到生产调优，掌握 MySQL 内核级知识

## 核心能力

### 1. InnoDB 引擎
- **存储结构**：表空间、段、区、页、行
- **索引结构**：B+Tree、聚簇索引、二级索引
- **事务机制**：ACID、MVCC、Undo Log
- **日志系统**：Redo Log、Undo Log、Binlog

### 2. 锁机制
- **锁类型**：Record Lock、Gap Lock、Next-Key Lock
- **锁算法**：IS、IX、S、X、Auto-inc
- **死锁处理**：检测、回滚、预防
- **锁优化**：减少锁范围、缩短持锁时间

### 3. 执行计划
- **解析过程**：语法解析、优化、执行
- **优化器**：Cost Model、索引选择、JOIN 顺序
- **Explain 解读**：type、key、rows、Extra
- **执行计划缓存**：Plan Cache、Prepared Statement

### 4. 性能调优
- **慢查询分析**：Slow Log、Performance Schema
- **索引优化**：最左前缀、覆盖索引、索引下推
- **查询优化**：重写 SQL、避免全表扫描
- **配置优化**：innodb_buffer_pool、max_connections

## 知识库引用

| 主题 | 文档 |
|------|------|
| InnoDB 内核 | `knowledge/mysql/mysql-innodb-deep.md` |
| 事务锁 | `knowledge/mysql/mysql-transaction-lock-deep.md` |
| 执行计划 | `knowledge/mysql/mysql-explain-optimization-deep.md` |
| 索引优化 | `knowledge/mysql/mysql-index-optimization-deep.md` |
| 内核深入 | `knowledge/mysql/mysql-kernel-deep.md` |
| 源码分析 | `knowledge/mysql/mysql-innodb-source-deep.md` |
| 生产排障 | `knowledge/mysql/mysql-production-troubleshooting.md` |
| 连接池 | `knowledge/fullstack/database-connection-pool-deep.md` |

## 使用场景

### 场景 1: 慢查询优化
1. 开启 Slow Log 捕获慢查询
2. 使用 EXPLAIN 分析执行计划
3. 优化索引或重写 SQL
4. 验证优化效果

### 场景 2: 死锁排查
1. 查看 SHOW ENGINE INNODB STATUS
2. 分析死锁日志
3. 优化事务顺序或锁范围
4. 添加适当的索引

### 场景 3: 性能调优
1. 使用 Performance Schema 定位瓶颈
2. 分析 Buffer Pool 命中率
3. 优化 innodb_buffer_pool_size
4. 调整 max_connections

## 关键配置

```ini
# InnoDB 核心配置
innodb_buffer_pool_size = 物理内存 × 70%
innodb_log_file_size = innodb_buffer_pool_size × 25%
innodb_flush_log_at_trx_commit = 1  # 安全性
innodb_io_capacity = 2000  # 根据磁盘性能调整

# 连接配置
max_connections = 500
thread_cache_size = 64

# 慢查询
slow_query_log = ON
long_query_time = 1
```

## 自测题

<details>
<summary>Q1: MVCC 是如何实现的？</summary>

**答案**：
1. **隐藏列**：每行有 DB_TRX_ID（事务 ID）和 DB_ROLL_PTR（回滚指针）
2. **Undo Log**：版本链，保存历史版本
3. **Read View**：快照读时生成，包含活跃事务列表
4. **可见性判断**：根据事务 ID 和 Read View 判断版本可见性
5. **幻读解决**：Next-Key Lock + MVCC 结合

</details>

<details>
<summary>Q2: Gap Lock 的作用是什么？为什么需要？</summary>

**答案**：
1. **防止幻读**：锁定范围，防止其他事务插入
2. **REPEATABLE READ**：MySQL 默认隔离级别需要 Gap Lock
3. **索引锁**：只在有索引的列上加 Gap Lock
4. **唯一索引**：退化到 Record Lock，不需要 Gap
5. **无索引**：锁定整个表（最坏情况）

</details>

<details>
<summary>Q3: 如何选择合适的索引？</summary>

**答案**：
1. **最左前缀**：复合索引遵循最左前缀原则
2. **高区分度**：选择区分度高的列
3. **覆盖索引**：查询字段都在索引中
4. **索引下推**：MySQL 5.6+ 优化
5. **避免过度索引**：写操作会变慢
6. **使用 EXPLAIN**：验证索引是否被使用

</details>
