# MySQL 索引与查询优化深度实战

> 深入 MySQL 索引原理、查询优化、执行计划分析。
> 包含真实生产环境优化案例。
> 适用对象：DBA、后端工程师、性能优化工程师

---

## 1. 索引数据结构

### 1.1 B+ 树结构

```
┌─────────────────────────────────────────────────────────────────┐
│                        B+ 树索引结构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ 根节点    │───►│ 中间节点  │───►│ 叶子节点  │                  │
│  │ (页1)    │    │ (页2)    │    │ (页3-10) │                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│       │               │               │    │    │                │
│       │               │               ▼    ▼    ▼                │
│       │               │         ┌──────────────────┐            │
│       │               │         │ 数据页 (实际数据) │            │
│       │               │         └──────────────────┘            │
│       │               │                                         │
│       └───────────────┴─────────────────────────────────────────┘
│                                                                 │
│  特点：                                                          │
│  1. 所有数据都在叶子节点                                        │
│  2. 叶子节点形成双向链表                                        │
│  3. 非叶子节点只存索引和指针                                    │
│  4. 树高度通常 2-4 层                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 索引类型对比

| 索引类型 | 数据结构 | 适用场景 | 性能特点 |
|----------|----------|----------|----------|
| 聚簇索引 | B+树 | 主键查询 | 最快，数据即索引 |
| 二级索引 | B+树 | 非主键查询 | 需回表查询 |
| 联合索引 | B+树 | 多列查询 | 最左前缀原则 |
| 哈希索引 | 哈希表 | 等值查询 | O(1)，不支持范围 |
| 全文索引 | 倒排索引 | 文本搜索 | 支持模糊匹配 |

---

## 2. 查询优化实战

### 2.1 执行计划分析

```sql
-- 查看执行计划
EXPLAIN FORMAT=JSON
SELECT u.name, o.amount 
FROM users u 
JOIN orders o ON u.id = o.user_id 
WHERE u.age > 25 
ORDER BY o.created_at DESC 
LIMIT 10;
```

**执行计划关键字段**：

| 字段 | 含义 | 优化方向 |
|------|------|----------|
| type | 连接类型 | 追求 const/eq_ref |
| key | 实际使用的索引 | 确保使用索引 |
| rows | 扫描行数 | 越小越好 |
| Extra | 额外信息 | 避免 filesort/temp |

### 2.2 常见优化案例

**案例 1：慢查询优化**

```sql
-- 优化前（15秒）
SELECT * FROM orders 
WHERE user_id = 12345 
ORDER BY created_at DESC 
LIMIT 20;

-- 优化后（0.01秒）
-- 添加联合索引
ALTER TABLE orders ADD INDEX idx_user_created (user_id, created_at);

-- 优化查询
SELECT id, user_id, amount, created_at 
FROM orders 
WHERE user_id = 12345 
ORDER BY created_at DESC 
LIMIT 20;
```

**案例 2：深分页优化**

```sql
-- 优化前（5秒，LIMIT 100000, 20）
SELECT * FROM products LIMIT 100000, 20;

-- 优化方案一：子查询
SELECT * FROM products 
WHERE id >= (
    SELECT id FROM products LIMIT 100000, 1
) LIMIT 20;

-- 优化方案二：延迟关联
SELECT p.* FROM products p
INNER JOIN (
    SELECT id FROM products LIMIT 100000, 20
) tmp ON p.id = tmp.id;
```

**案例 3：类型转换导致索引失效**

```sql
-- 错误：字符串字段用数字查询
SELECT * FROM users WHERE phone = 13800138000;  -- phone 是 VARCHAR

-- 正确
SELECT * FROM users WHERE phone = '13800138000';
```

---

## 3. 索引设计原则

### 3.1 最左前缀原则

```sql
-- 联合索引 (a, b, c)
-- 能使用的场景：
WHERE a = 1              -- ✅ 使用索引
WHERE a = 1 AND b = 2    -- ✅ 使用索引
WHERE a = 1 AND b = 2 AND c = 3  -- ✅ 使用索引
WHERE b = 2              -- ❌ 不使用索引（缺少 a）
WHERE a = 1 AND c = 3    -- ⚠️ 只用 a 列索引
```

### 3.2 索引选择原则

```
1. 高选择性的列放前面
   示例：status（0/1） vs user_id（百万级）
   索引顺序：(user_id, status)

2. 等值查询列放前面
   示例：WHERE type = ? AND created_at > ?
   索引顺序：(type, created_at)

3. 范围查询列放后面
   示例：WHERE status = ? AND created_at > ?
   索引顺序：(status, created_at)
```

### 3.3 覆盖索引

```sql
-- 使用覆盖索引避免回表
-- 原查询
SELECT id, name, age FROM users WHERE status = 1;

-- 添加覆盖索引
ALTER TABLE users ADD INDEX idx_status_name_age (status, name, age);

-- 优化后：只需扫描索引，不需要回表
```

---

## 4. 锁机制

### 4.1 锁类型

| 锁类型 | 说明 | 场景 |
|--------|------|------|
| 表锁 | 锁定整张表 | 批量操作 |
| 行锁 | 锁定单行记录 | 高并发更新 |
| 间隙锁 | 锁定索引间隙 | 防止幻读 |
| 临键锁 | 行锁+间隙锁 | 可重复读 |

### 4.2 死锁排查

```sql
-- 查看死锁信息
SHOW ENGINE INNODB STATUS;

-- 查看当前锁
SELECT * FROM information_schema.innodb_locks;

-- 查看等待锁
SELECT * FROM information_schema.innodb_lock_waits;
```

---

## 5. 实战优化案例

### 5.1 案例：订单查询优化

**问题**：订单列表查询超时

```sql
-- 优化前（8秒）
SELECT o.id, o.amount, u.name 
FROM orders o 
JOIN users u ON o.user_id = u.id 
WHERE o.status = 1 
AND o.created_at BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY o.created_at DESC 
LIMIT 20;
```

**优化步骤**：

1. 分析执行计划
2. 添加复合索引
3. 优化查询结构

```sql
-- 添加索引
ALTER TABLE orders ADD INDEX idx_status_created (status, created_at);

-- 优化查询
SELECT o.id, o.amount, u.name 
FROM orders o 
JOIN users u ON o.id = u.order_id 
WHERE o.status = 1 
AND o.created_at >= '2024-01-01' 
AND o.created_at < '2025-01-01'
ORDER BY o.created_at DESC 
LIMIT 20;
```

**优化结果**：8秒 → 0.05秒

---

## 6. 总结

### 6.1 优化 Checklist

- [ ] 慢查询日志开启
- [ ] 执行计划分析
- [ ] 索引设计合理
- [ ] 避免 SELECT *
- [ ] 避免类型转换
- [ ] 深分页优化
- [ ] 批量操作优化
- [ ] 锁竞争检查

### 6.2 性能指标

| 指标 | 目标值 |
|------|--------|
| 查询延迟 P99 | < 100ms |
| 慢查询比例 | < 1% |
| 索引命中率 | > 95% |
| 锁等待时间 | < 10ms |

---

*最后更新：2026-08-11*
*作者：Ryan*
