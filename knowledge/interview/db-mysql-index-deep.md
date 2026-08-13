# MySQL索引优化 - 资深专家深度实现

## 一、B+树索引结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         B+树索引结构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                          ┌───────┐                                       │
│                          │ 根节点  │                                       │
│                          └───┬───┘                                       │
│                     ┌───────┼───────┐                                   │
│                     ▼       ▼       ▼                                   │
│                ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│                │ 内部节点 │ │ 内部节点 │ │ 内部节点 │                    │
│                └────┬────┘ └────┬────┘ └────┬────┘                    │
│                     │          │          │                              │
│              ┌──────┼──┐  ┌────┼──┐  ┌───┼──┐                          │
│              ▼      ▼  │  ▼    ▼  │  ▼   ▼  │                        │
│           ┌─────┐ ┌───┴───┐ ┌─────┐ ┌───┴───┐ ┌─────┐                 │
│           │叶子节点│ │叶子节点 │ │叶子节点│ │叶子节点 │ │叶子节点│           │
│           └──┬──┘ └───┬───┘ └──┬──┘ └───┬───┘ └──┬──┘                 │
│              │        │        │        │        │                       │
│              ▼        ▼        ▼        ▼        ▼                       │
│           ┌──────────────────────────────────────────┐                 │
│           │ 数据页 (按索引顺序排列)                      │                 │
│           └──────────────────────────────────────────┘                 │
│                                                                         │
│   特点:                                                                  │
│   • 所有数据都在叶子节点                                                   │
│   • 叶子节点通过指针连接，支持范围查询                                       │
│   • 非叶子节点只存储索引值                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、索引类型

### 2.1 聚簇索引 vs 非聚簇索引

```sql
-- 聚簇索引: 数据按索引顺序存储（InnoDB主键）
CREATE TABLE users (
    id INT PRIMARY KEY,      -- 聚簇索引
    name VARCHAR(50),
    email VARCHAR(100)
);

-- 非聚簇索引: 单独存储索引，指向数据行
CREATE INDEX idx_email ON users(email);
```

### 2.2 复合索引

```sql
-- 最左前缀原则
CREATE INDEX idx_name_age ON users(name, age, city);

-- 以下查询可以使用索引:
SELECT * FROM users WHERE name = 'Ryan';                    -- ✅
SELECT * FROM users WHERE name = 'Ryan' AND age = 30;       -- ✅
SELECT * FROM users WHERE name = 'Ryan' AND age = 30 AND city = 'BJ'; -- ✅

-- 以下查询不能使用完整索引:
SELECT * FROM users WHERE age = 30;                        -- ❌ (跳过name)
SELECT * FROM users WHERE city = 'BJ';                     -- ❌ (跳过name,age)
```

## 三、执行计划分析

```sql
-- 使用EXPLAIN分析查询
EXPLAIN SELECT * FROM orders 
WHERE user_id = 123 
AND status = 'paid'
ORDER BY create_time DESC 
LIMIT 10;

-- 关键字段解读:
-- type: system/const/eq_ref/ref/range/index/all
-- key: 实际使用的索引
-- rows: 预估扫描行数
-- Extra: Using filesort/Using temporary/Using index
```

### 3.1 访问类型说明

| 类型 | 含义 | 性能 |
|------|------|------|
| system | 表只有一行 | 最优 |
| const | 主键/唯一索引 | 优秀 |
| eq_ref | 唯一索引 | 优秀 |
| ref | 普通索引 | 良好 |
| range | 索引范围扫描 | 一般 |
| index | 全索引扫描 | 较差 |
| all | 全表扫描 | 最差 |

## 四、索引优化实战

### 4.1 覆盖索引

```sql
-- 原始查询（需要回表）
SELECT * FROM orders WHERE user_id = 123;

-- 优化：使用覆盖索引
SELECT id, amount FROM orders 
WHERE user_id = 123 
AND status = 'paid';
-- 创建覆盖索引
ALTER TABLE orders ADD INDEX idx_user_status (user_id, status, amount);
```

### 4.2 索引下推

```sql
-- MySQL 5.6+ 特性
-- 在索引层过滤，减少回表次数

-- 查询: name LIKE '张%' AND age > 30
-- 传统: 索引扫描 → 回表 → 应用层过滤
-- ICPS: 索引层同时过滤 age > 30 → 回表
```

### 4.3 排序优化

```sql
-- 避免文件排序
CREATE INDEX idx_user_create ON orders(user_id, create_time);

-- 以下查询可以使用索引排序
SELECT * FROM orders WHERE user_id = 123 ORDER BY create_time;
-- ✅ 利用索引顺序，无需额外排序
```

## 五、常见误区

```go
package index

// 误区1: 索引越多越好
// ❌ 错误: 创建过多索引影响写入性能
// ✅ 正确: 根据查询频率和写入频率平衡

// 误区2: 避免在索引列上使用函数
// ❌ 错误
SELECT * FROM users WHERE YEAR(create_time) = 2024;
// ✅ 正确
SELECT * FROM users WHERE create_time BETWEEN '2024-01-01' AND '2024-12-31';

// 误区3: 避免前缀模糊查询
// ❌ 错误
SELECT * FROM users WHERE name LIKE '%ryan%';
// ✅ 正确（使用全文索引）
SELECT * FROM users WHERE MATCH(name) AGAINST('ryan');

// 误区4: 不等于(!= 或 <>)可能失效
// ❌ 低效
SELECT * FROM users WHERE status != 1;
// ✅ 高效（如果1很少）
SELECT * FROM users WHERE status = 0 OR status = 2;
```

## 六、自测题

1. 什么是覆盖索引？如何使用？
2. 解释最左前缀原则
3. 如何判断是否需要添加索引？

---

## 参考文档

- [MySQL索引优化](https://dev.mysql.com/doc/refman/8.0/en/access-control.html)
- [InnoDB存储引擎](https://dev.mysql.com/doc/refman/8.0/en/innodb-index-types.html)
