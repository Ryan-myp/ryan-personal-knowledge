# MySQL查询优化 - 资深专家深度实现

## 一、索引优化

### 1.1 最左前缀法则

```sql
-- 联合索引 (a, b, c)
-- 符合最左前缀的查询:
WHERE a = 1
WHERE a = 1 AND b = 2
WHERE a = 1 AND b = 2 AND c = 3

-- 不符合的查询:
WHERE b = 2  -- 跳过a
WHERE a = 1 AND c = 3  -- 跳过b
```

### 1.2 覆盖索引

```sql
-- 避免回表
SELECT id, name FROM users WHERE status = 1;
-- 创建索引: (status, name)
```

## 二、查询优化

### 2.1 EXPLAIN分析

```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 100;
-- 关注: type, key, rows, Extra
```

### 2.2 避免SELECT *

```sql
-- 差
SELECT * FROM users WHERE id = 1;

-- 好
SELECT id, name, email FROM users WHERE id = 1;
```

## 三、分库分表

```
单表优化 → 读写分离 → 分库分表

水平分表: 按user_id取模
垂直分表: 大字段分离
```

## 四、面试高频题

### Q1: 如何优化慢查询？

```
A:
1. 使用EXPLAIN分析
2. 添加合适索引
3. 优化查询语句
4. 考虑分库分表
```

### Q2: 什么是回表？

```
A: 通过主键查数据时，二级索引需要回主键索引再查。
```

## 五、自测题

1. 设计一个高并发订单表
2. 如何优化分页查询？

---

## 参考文档

- [MySQL官方文档](https://dev.mysql.com/doc/)
