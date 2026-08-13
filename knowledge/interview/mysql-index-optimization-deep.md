# MySQL索引优化 - 资深专家深度实现

## 一、索引类型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MySQL索引类型                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   主键索引 (PRIMARY KEY)                                                 │
│   • 唯一标识，不允许NULL                                                   │
│   • 聚簇索引，数据按主键排序                                               │
│                                                                         │
│   唯一索引 (UNIQUE)                                                      │
│   • 允许NULL，但值唯一                                                     │
│   • 加速查询                                                              │
│                                                                         │
│   普通索引 (INDEX)                                                       │
│   • 无限制，可重复                                                          │
│   • 最常用                                                                │
│                                                                         │
│   联合索引 (COMPOSITE)                                                   │
│   • 多列组合                                                               │
│   • 最左前缀原则                                                            │
│                                                                         │
│   全文索引 (FULLTEXT)                                                    │
│   • MyISAM/InnoDB                                                          │
│   • 搜索引擎                                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、B+树实现

```sql
-- 创建索引
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_order_status_time ON orders(status, created_at);

-- 联合索引最左前缀
SELECT * FROM orders WHERE status = 'pending'; -- ✅ 使用索引
SELECT * FROM orders WHERE created_at > '2024-01-01'; -- ❌ 不使用索引
SELECT * FROM orders WHERE status = 'pending' AND created_at > '2024-01-01'; -- ✅ 使用索引
```

## 三、查询优化

```sql
-- EXPLAIN分析
EXPLAIN SELECT * FROM orders WHERE status = 'pending' AND user_id = 123;

-- 输出关键字段:
-- type: ref / range / index / ALL
-- key: 实际使用的索引
-- rows: 扫描行数
-- Extra: Using index / Using filesort / Using temporary
```

## 四、面试高频题

### Q1: 索引为什么快？

```
A:
1. B+树减少IO次数
2. 范围查询高效
3. 有序存储
```

### Q2: 如何选择合适的索引？

```
A:
1. 高频查询字段
2. 区分度高
3. 避免过度索引
```

## 五、自测题

1. 解释B+树结构
2. 如何实现最左前缀？
3. 如何优化慢查询？

---

## 参考文档

- [MySQL官方文档](https://dev.mysql.com/doc/refman/8.0/en/optimization.html)
- [InnoDB存储引擎](https://dev.mysql.com/doc/refman/8.0/en/innodb-storage-engine.html)
