# MySQL索引优化 - 资深专家深度实现

## 一、B+树结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      B+树索引结构                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│         [根节点]                                                          │
│            │                                                              │
│      ┌────┼────┐                                                          │
│      │         │                                                         │
│   [内部节点] [内部节点]                                                   │
│   /  \     /  \                                                        │
│ ┌───┐ ┌───┐ ┌───┐ ┌───┐                                              │
│ │页1│ │页2│ │页3│ │页4│  ← 叶子节点(数据页)                               │
│ └───┘ └───┘ └───┘ └───┘                                               │
│                                                                         →
│   特点:                                                                  │
│   ├── 所有数据在叶子节点                                                   │
│   ├── 叶子节点双向链表                                                      │
│   └── 范围查询高效                                                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、索引优化策略

```sql
-- 最左前缀原则
CREATE INDEX idx_user ON orders(user_id, order_time, status);

-- 覆盖索引
SELECT user_id, order_time FROM orders WHERE user_id = 123;

-- 索引下推
SELECT * FROM orders 
WHERE user_id = 123 AND order_time > '2024-01-01';

-- 避免索引失效
-- ❌ 错误: 函数操作
SELECT * FROM orders WHERE YEAR(order_time) = 2024;
-- ✅ 正确: 范围查询
SELECT * FROM orders WHERE order_time >= '2024-01-01' AND order_time < '2025-01-01';
```

## 三、面试高频题

### Q1: 为什么用B+树？

```
A:
1. 多叉树减少高度
2. 叶子节点链表支持范围查询
3. 磁盘IO效率高
```

### Q2: 如何选择索引？

```
A:
1. 区分度高
2. 最左前缀
3. 避免过多索引
```

## 四、自测题

1. 解释B+树结构
2. 如何实现覆盖索引？
3. 如何处理索引失效？

---

## 参考文档

- [InnoDB存储引擎](https://dev.mysql.com/doc/refman/8.0/en/innodb-storage-engine.html)
- [MySQL索引优化](https://dev.mysql.com/doc/refman/8.0/en/optimization-indexes.html)
