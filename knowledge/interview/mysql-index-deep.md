# MySQL索引优化深度实现 --- 资深专家深度实现

## 概述

MySQL索引是提升查询性能的核心手段，但错误的索引设计反而会导致性能下降。本文深入剖析B+树索引原理、索引设计原则和生产环境优化实践。

## 一、B+树索引原理

### 1.1 索引数据结构

```
┌─────────────────────────────────────────────────────────┐
│                    B+树索引结构                          │
├─────────────────────────────────────────────────────────┤
│                         Root                           │
│                    ┌─────────┐                          │
│                    │  页1   │ (指针节点)                 │
│                    └───┬─────┘                          │
│              ┌────────┼────────┐                       │
│           ┌──▼──┐  ┌──▼──┐  ┌──▼──┐                  │
│           │ 页2 │  │ 页3 │  │ 页4 │ (中间层)           │
│           └──┬──┘  └──┬──┘  └──┬──┘                  │
│      ┌───────┼───────┼───────┼───────┐               │
│   ┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐          │
│   │叶1 │ │叶2 │ │叶3 │ │叶4 │ │叶5 │ (叶子层)       │
│   └────┘ └────┘ └────┘ └────┘ └────┘               │
│   [id:1] [id:2] [id:3] [id:4] [id:5]                 │
└─────────────────────────────────────────────────────────┘
```

### 1.2 索引节点结构

```sql
-- InnoDB索引页结构
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(64),
    email VARCHAR(128),
    created_at DATETIME,
    INDEX idx_name (name),
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- 查看索引信息
SHOW INDEX FROM users;
-- +-------+------------+----------+--------------+-------------+-----------+
-- | Table | Non_unique | Key_name | Seq_in_index | Column_name | Collation |
-- +-------+------------+----------+--------------+-------------+-----------+
-- | users | 0          | PRIMARY  | 1            | id          | A         |
-- | users | 1          | idx_name | 1            | name        | A         |
-- | users | 1          | idx_email| 1            | email       | A         |
-- +-------+------------+----------+--------------+-------------+-----------+
```

## 二、索引类型详解

### 2.1 主键索引 vs 二级索引

```sql
-- 主键索引 (聚簇索引)
-- 数据存储在叶子节点
SELECT * FROM users WHERE id = 1;

-- 二级索引 (非聚簇索引)
-- 叶子节点存储主键值，需要回表
SELECT * FROM users WHERE name = 'ryan';

-- 覆盖索引 (避免回表)
SELECT id, name FROM users WHERE name = 'ryan';
-- 只查询索引列，不需要回表
```

### 2.2 联合索引

```sql
-- 最左前缀原则
CREATE INDEX idx_user ON users(name, email, created_at);

-- ✅ 符合最左前缀
SELECT * FROM users WHERE name = 'ryan';
SELECT * FROM users WHERE name = 'ryan' AND email = 'ryan@example.com';
SELECT * FROM users WHERE name = 'ryan' AND created_at > '2024-01-01';

-- ❌ 不符合最左前缀 (跳过name)
SELECT * FROM users WHERE email = 'ryan@example.com';
SELECT * FROM users WHERE created_at > '2024-01-01';

-- 隐式类型转换导致索引失效
SELECT * FROM users WHERE name = 123;  -- name是VARCHAR
```

## 三、EXPLAIN分析

### 3.1 执行计划解读

```sql
EXPLAIN SELECT * FROM users WHERE name = 'ryan';
-- +----+-------------+-------+------------+-------+---------------+
-- | id | select_type | table | partitions | type  | possible_keys |
-- +----+-------------+-------+------------+-------+---------------+
-- |  1 | SIMPLE      | users | NULL       | ref   | idx_name      |
-- +----+-------------+-------+------------+-------+---------------+

-- type字段含义:
-- system > const > eq_ref > ref > range > index > ALL
-- 从左到右性能递减
```

### 3.2 常见type分析

```sql
-- ref: 非唯一索引查找
EXPLAIN SELECT * FROM users WHERE name = 'ryan';
-- type: ref, key: idx_name

-- range: 范围查询
EXPLAIN SELECT * FROM users WHERE id > 100 AND id < 200;
-- type: range, key: PRIMARY

-- index: 全索引扫描
EXPLAIN SELECT id FROM users;
-- type: index (覆盖索引)

-- ALL: 全表扫描 (需要优化)
EXPLAIN SELECT * FROM users WHERE email = 'test@test.com';
-- 没有索引，type: ALL
```

### 3.3 key_len计算

```sql
-- VARCHAR(n) CHARACTER SET utf8mb4
-- key_len = n * 4 (utf8mb4最大4字节) + 2 (变长长度) + 1 (NULL标记)

-- 示例
CREATE TABLE test (
    id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    PRIMARY KEY (id),
    INDEX idx_name (name),
    INDEX idx_email (email)
);

-- 查询 name = 'test'
-- key_len = 100 * 4 + 2 = 402

-- 查询 name = 'test' AND email = 'test@test.com'
-- key_len = 402 + 100 * 4 + 2 + 1 = 805
```

## 四、索引设计原则

### 4.1 高选择性列

```sql
-- 选择度高: 唯一值/总记录数接近1
-- 低选择度: 唯一值/总记录数很小 (如性别)

-- ✅ 适合建索引
ALTER TABLE orders ADD INDEX idx_user_id (user_id);
-- user_id有10万不同值，总记录100万，选择度0.1

-- ❌ 不适合建索引
ALTER TABLE orders ADD INDEX idx_gender (gender);
-- gender只有2个值，选择度0.000002
```

### 4.2 索引覆盖

```sql
-- 避免SELECT *，只查询需要的列
-- ❌ 低效
SELECT * FROM users WHERE name = 'ryan';
-- 需要回表获取所有列

-- ✅ 高效
SELECT id, name, email FROM users WHERE name = 'ryan';
-- 可能使用覆盖索引
```

### 4.3 前缀索引

```sql
-- 对长字符串索引
ALTER TABLE users ADD INDEX idx_email_prefix (email(10));
-- 只索引前10个字符

-- 查看前缀索引效果
SELECT COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) as selectivity
FROM users;
-- 选择度 > 0.1 推荐使用前缀索引
```

## 五、性能调优

### 5.1 慢查询分析

```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;  -- 1秒以上记录

-- 使用mysqldumpslow分析
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log
-- 按时间排序，显示top 10慢查询

-- 使用pt-query-digest
pt-query-digest /var/log/mysql/slow.log
```

### 5.2 索引维护

```sql
-- 分析索引使用情况
SELECT 
    table_name,
    index_name,
    cardinality
FROM information_schema.statistics
WHERE table_schema = 'your_db';

-- 删除未使用的索引
ALTER TABLE users DROP INDEX idx_unused;

-- 优化表（碎片整理）
OPTIMIZE TABLE users;
-- 注意：会锁表，生产环境慎用
```

### 5.3 分区表

```sql
-- 按时间分区
CREATE TABLE orders (
    id INT NOT NULL,
    created_at DATE NOT NULL,
    amount DECIMAL(10,2)
) PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026)
);

-- 查询时自动分区裁剪
SELECT * FROM orders WHERE created_at = '2024-06-01';
-- 只扫描p2024分区
```

## 六、面试高频题

### 6.1 高频问题

**Q1: B+树为什么适合做数据库索引？**

A: 
- 多叉树降低树高，减少IO次数
- 叶子节点链表连接，支持范围查询
- 非叶子节点只存键值，单页可存更多索引项

**Q2: 什么情况下索引会失效？**

A:
- 违反最左前缀原则
- 对索引列进行函数运算
- 隐式类型转换
- LIKE '%xxx' 前缀通配
- OR条件中部分无索引

**Q3: 如何判断索引是否有效？**

A:
- EXPLAIN分析执行计划
- 查看key列是否使用预期索引
- 检查rows是否合理
- 监控慢查询日志

### 6.2 自测题

1. 画出B+树索引的结构图
2. 解释最左前缀原则
3. 分析以下查询能否使用索引
4. 设计一个电商订单表的索引方案
5. 解释覆盖索引的工作原理

---

**创建时间**: 2026-10-16
**作者**: Ryan
**领域**: Interview / 数据库
**关键词**: mysql, index, b-tree, explain, optimization
