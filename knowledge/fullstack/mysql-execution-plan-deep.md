# MySQL 执行计划深度解析

> 深入 MySQL 查询优化：EXPLAIN 详解、索引优化、查询改写。
> 实战案例，包含生产环境问题排查。
> 适用对象：DBA、后端工程师、性能优化工程师

---

## 1. EXPLAIN 详解

### 1.1 输出字段

```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 100;

-- 输出字段说明：
-- id: 查询序号
-- select_type: 查询类型
-- table: 表名
-- partitions: 匹配的分区
-- type: 访问类型
-- possible_keys: 可能的索引
-- key: 实际使用的索引
-- key_len: 索引长度
-- ref: 索引引用的列
-- rows: 估计扫描行数
-- filtered: 过滤比例
-- Extra: 额外信息
```

### 1.2 访问类型

```
type 类型（从优到差）：

system > const > eq_ref > ref > range > index > ALL

-- system: 表只有一行（系统表）
-- const: 常量查询，最多匹配一行
-- eq_ref: 唯一索引查询
-- ref: 非唯一索引查询
-- range: 索引范围扫描
-- index: 全索引扫描
-- ALL: 全表扫描（最差）
```

### 1.3 Extra 字段

```
Extra 常见值：

-- Using index: 覆盖索引
-- Using where: 使用 WHERE 条件
-- Using temporary: 使用临时表
-- Using filesort: 需要文件排序
-- Impossible where: WHERE 总是假
-- Distinct: 去重
```

---

## 2. 索引优化

### 2.1 最左前缀原则

```sql
-- 联合索引 (a, b, c)

-- ✅ 可以使用索引
SELECT * FROM t WHERE a = 1;
SELECT * FROM t WHERE a = 1 AND b = 2;
SELECT * FROM t WHERE a = 1 AND b = 2 AND c = 3;
SELECT * FROM t WHERE a = 1 AND c = 3;

-- ❌ 不能使用索引
SELECT * FROM t WHERE b = 2;
SELECT * FROM t WHERE c = 3;
SELECT * FROM t WHERE b = 2 AND c = 3;
```

### 2.2 覆盖索引

```sql
-- 覆盖索引：查询的列都在索引中

-- ❌ 需要回表
SELECT * FROM users WHERE username = 'ryan';

-- ✅ 覆盖索引，不需要回表
SELECT id, username FROM users WHERE username = 'ryan';

-- 创建覆盖索引
ALTER TABLE users ADD INDEX idx_username (username, id);
```

### 2.3 索引下推

```
索引下推 (ICP - Index Condition Pushdown)

传统方式：
┌─────────┐    ┌─────────┐    ┌─────────┐
│ 索引扫描 │───►│ 回表查询 │───►│ WHERE过滤│
└─────────┘    └─────────┘    └─────────┘

索引下推方式：
┌─────────┐    ┌─────────┐    ┌─────────┐
│ 索引扫描 │───►│ WHERE过滤│───►│ 回表查询 │
│ (ICP)   │    │ 在存储引擎│    │          │
└─────────┘    └─────────┘    └─────────┘
```

---

## 3. 查询优化

### 3.1 慢查询分析

```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query_log%';
SHOW VARIABLES LIKE 'long_query_time';
```

### 3.2 优化示例

```sql
-- 优化前：全表扫描
EXPLAIN SELECT * FROM orders WHERE create_time > '2024-01-01';
-- type: ALL, rows: 1000000

-- 优化后：索引范围扫描
ALTER TABLE orders ADD INDEX idx_create_time (create_time);
EXPLAIN SELECT * FROM orders WHERE create_time > '2024-01-01';
-- type: range, rows: 10000

-- 进一步优化：覆盖索引
EXPLAIN SELECT id, user_id FROM orders WHERE create_time > '2024-01-01';
-- Extra: Using index (覆盖索引)
```

### 3.3 分页优化

```sql
-- ❌ 深分页性能差
SELECT * FROM orders LIMIT 100000, 10;

-- ✅ 子查询优化
SELECT * FROM orders 
WHERE id >= (SELECT id FROM orders LIMIT 100000, 1) 
LIMIT 10;

-- ✅ 延迟关联
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders LIMIT 100000, 1
) t ON o.id = t.id;
```

---

## 4. 实战案例

### 4.1 复杂查询优化

```sql
-- 优化前：子查询 + 文件排序
EXPLAIN SELECT * FROM orders 
WHERE user_id IN (SELECT user_id FROM users WHERE status = 1)
ORDER BY create_time DESC
LIMIT 10;

-- 优化方案1：JOIN 替代子查询
EXPLAIN SELECT o.* FROM orders o
INNER JOIN users u ON o.user_id = u.user_id
WHERE u.status = 1
ORDER BY o.create_time DESC
LIMIT 10;

-- 优化方案2：添加索引
ALTER TABLE users ADD INDEX idx_status (status);
ALTER TABLE orders ADD INDEX idx_user_time (user_id, create_time);

-- 优化方案3：覆盖索引
EXPLAIN SELECT o.id, o.user_id, o.create_time FROM orders o
INNER JOIN users u ON o.user_id = u.user_id
WHERE u.status = 1
ORDER BY o.create_time DESC
LIMIT 10;
-- Extra: Using index (覆盖索引)
```

### 4.2 聚合查询优化

```sql
-- 优化前：全表聚合
EXPLAIN SELECT user_id, COUNT(*) as cnt 
FROM orders 
GROUP BY user_id;

-- 优化方案：添加索引
ALTER TABLE orders ADD INDEX idx_user (user_id);

-- 优化后：索引聚合
EXPLAIN SELECT user_id, COUNT(*) as cnt 
FROM orders 
GROUP BY user_id;
-- type: index, Extra: Using index
```

---

## 5. 监控诊断

### 5.1 性能 Schema

```sql
-- 查看表访问统计
SELECT * FROM sys.schema_table_statistics;

-- 查看索引使用情况
SELECT * FROM sys.schema_unused_indexes;

-- 查看全文索引
SELECT * FROM sys.schema_index_statistics;
```

### 5.2 慢查询分析

```bash
# 使用 mysqldumpslow 分析
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

# 使用 pt-query-digest
pt-query-digest slow.log
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| EXPLAIN | 分析执行计划 |
| 索引优化 | 最左前缀/覆盖索引 |
| 查询优化 | JOIN/子查询改写 |
| 监控诊断 | Performance Schema |

### 6.2 最佳实践

- [ ] 合理使用 EXPLAIN
- [ ] 遵循最左前缀原则
- [ ] 使用覆盖索引
- [ ] 避免深分页
- [ ] 定期分析慢查询

---

*最后更新：2026-08-11*
*作者：Ryan*
