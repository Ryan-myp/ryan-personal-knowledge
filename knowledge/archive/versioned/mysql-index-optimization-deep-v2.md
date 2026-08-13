# MySQL 索引优化深度实战

> 深入 MySQL 索引优化：B+树原理、索引类型、查询优化、执行计划分析。
> 源码级分析，包含生产环境优化案例。
> 适用对象：DBA、后端工程师、性能优化工程师

---

## 1. B+ 树索引原理

### 1.1 数据结构

```
┌─────────────────────────────────────────────────────────────┐
│                    B+ 树结构                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌──────┐                                 │
│                    │ Root │ (根节点)                         │
│                    └──┬───┘                                 │
│                       │                                     │
│              ┌────────┼────────┐                           │
│              ▼        ▼        ▼                           │
│         ┌────────┐ ┌────────┐ ┌────────┐                  │
│         │Leaf 1│ │Leaf 2│ │Leaf 3│                  │
│         └───┬────┘ └───┬────┘ └───┬────┘                  │
│             │          │          │                         │
│       ┌─────┴──┐  ┌───┴──┐  ┌───┴──┐                     │
│       ▼        ▼  ▼      ▼  ▼      ▼                     │
│    ┌──┐    ┌──┐ ┌──┐  ┌──┐ ┌──┐  ┌──┐                   │
│    │1 │    │4 │ │7 │  │2 │ │5 │  │8 │  (数据页)           │
│    └──┘    └──┘ └──┘  └──┘ └──┘  └──┘                   │
│                                                             │
│  特点：                                                      │
│  ├── 所有数据都在叶子节点                                    │
│  ├── 叶子节点形成链表                                        │
│  └── 非叶子节点只存储索引                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 索引类型对比

```
┌─────────────────────────────────────────────────────────────┐
│                    索引类型对比                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  聚簇索引 (Clustered Index)                                  │
│  ──────────────────────────                                  │
│  ├── 数据存储在叶子节点                                      │
│  ├── 每张表只能有一个                                        │
│  └── 主键索引就是聚簇索引                                    │
│                                                             │
│  二级索引 (Secondary Index)                                  │
│  ──────────────────────────                                  │
│  ├── 叶子节点存储主键值                                      │
│  ├── 需要回表查询                                            │
│  └── 可以有多个                                              │
│                                                             │
│  联合索引 (Composite Index)                                  │
│  ──────────────────────────                                  │
│  ├── 多个列组成的索引                                        │
│  └── 遵循最左前缀原则                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 索引优化策略

### 2.1 最左前缀原则

```sql
-- 联合索引 (a, b, c)

-- ✅ 可以使用索引
SELECT * FROM t WHERE a = 1;
SELECT * FROM t WHERE a = 1 AND b = 2;
SELECT * FROM t WHERE a = 1 AND b = 2 AND c = 3;
SELECT * FROM t WHERE a = 1 AND c = 3;  -- a匹配，c也匹配

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

## 3. 执行计划分析

### 3.1 EXPLAIN 输出

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

### 3.2 访问类型

```
type 类型（从优到差）：

system > const > eq_ref > ref > range > index > ALL

-- system: 表只有一行（系统表）
-- const: 常量查询，最多匹配一行
-- eq_ref: 唯一索引查询
-- ref: 非唯一索引查询
-- range: 索引范围扫描
-- index: 全索引扫描
-- ALL: 全表扫描
```

### 3.3 优化示例

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

---

## 4. 实战案例

### 4.1 慢查询优化

```sql
-- 慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- 优化前
SELECT * FROM orders 
WHERE user_id = 100 
AND status = 1 
ORDER BY create_time DESC 
LIMIT 10;
-- 执行时间: 5.2s

-- 创建联合索引
ALTER TABLE orders ADD INDEX idx_user_status_time (user_id, status, create_time);

-- 优化后
-- 执行时间: 0.02s
```

### 4.2 分页优化

```sql
-- ❌ 深分页性能差
SELECT * FROM orders LIMIT 100000, 10;
-- 需要扫描100010行

-- ✅ 子查询优化
SELECT * FROM orders 
WHERE id >= (SELECT id FROM orders LIMIT 100000, 1) 
LIMIT 10;

-- ✅ 延迟关联
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders LIMIT 100000, 10
) t ON o.id = t.id;
```

---

## 5. 索引设计原则

### 5.1 选择原则

```
1. 高频查询列
   - WHERE条件
   - ORDER BY
   - GROUP BY

2. 区分度高的列
   - 唯一索引 > 普通索引
   - 低基数列不适合单独建索引

3. 联合索引顺序
   - 等值查询在前
   - 范围查询在后
   - 高频查询在前
```

### 5.2 避免陷阱

```sql
-- ❌ 函数操作导致索引失效
SELECT * FROM orders WHERE YEAR(create_time) = 2024;

-- ✅ 范围查询
SELECT * FROM orders WHERE create_time >= '2024-01-01' 
AND create_time < '2025-01-01';

-- ❌ LIKE 前缀通配符
SELECT * FROM users WHERE username LIKE '%ryan%';

-- ✅ 前缀匹配
SELECT * FROM users WHERE username LIKE 'ryan%';

-- ❌ 隐式类型转换
SELECT * FROM orders WHERE order_no = 123456;  -- order_no是字符串

-- ✅ 显式类型转换
SELECT * FROM orders WHERE order_no = '123456';
```

---

## 6. 监控与诊断

### 6.1 性能_schema

```sql
-- 查看表访问统计
SELECT * FROM sys.schema_table_statistics;

-- 查看索引使用情况
SELECT * FROM sys.schema_unused_indexes;

-- 查看全文索引
SELECT * FROM sys.schema_index_statistics;
```

### 6.2 慢查询分析

```sql
-- 使用 mysqldumpslow 分析
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

-- 使用 pt-query-digest
pt-query-digest slow.log
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| B+树 | 多路平衡树 |
| 聚簇索引 | 数据与索引合一 |
| 二级索引 | 回表查询 |
| 联合索引 | 最左前缀 |

### 7.2 最佳实践

- [ ] 选择合适的索引类型
- [ ] 遵循最左前缀原则
- [ ] 使用覆盖索引
- [ ] 避免索引失效
- [ ] 定期分析慢查询

---

*最后更新：2026-08-11*
*作者：Ryan*
