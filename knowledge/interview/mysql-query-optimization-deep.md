# MySQL查询优化 - 资深专家深度实现

## 一、优化层次

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MySQL 查询优化金字塔                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                        ┌─────────┐                                      │
│                        │ SQL写法  │ ← 最高优先级                         │
│                        └────┬────┘                                      │
│                     ┌───────┴───────┐                                   │
│                     │ 索引设计      │                                     │
│                     └───────┬───────┘                                   │
│                  ┌──────────┴──────────┐                                │
│                  │ 表结构设计          │                                  │
│                  └──────────┬──────────┘                                │
│               ┌─────────────┴─────────────┐                             │
│               │ 配置参数                  │                               │
│               └─────────────┬─────────────┘                             │
│            ┌────────────────┴────────────────┐                          │
│            │ 硬件/架构                       │                           │
│            └─────────────────────────────────┘                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、执行计划分析

```sql
-- 查看执行计划
EXPLAIN SELECT * FROM orders WHERE user_id = 123;

-- 关键字段说明
-- id: 查询序号，越大优先级越高
-- select_type: 查询类型
-- table: 表名
-- type: 访问类型 (system > const > eq_ref > ref > range > index > ALL)
-- possible_keys: 可能使用的索引
-- key: 实际使用的索引
-- rows: 扫描行数
-- Extra: 额外信息
```

## 三、索引优化

```sql
-- 最左前缀原则
ALTER TABLE orders ADD INDEX idx_user_date_status (user_id, order_date, status);

-- 覆盖索引
SELECT id, name FROM users WHERE email = 'test@example.com';
-- 创建覆盖索引
ALTER TABLE users ADD INDEX idx_email_name (email, name);

-- 避免索引失效
-- ❌ 错误：对索引列使用函数
SELECT * FROM users WHERE YEAR(create_time) = 2024;
-- ✅ 正确：范围查询
SELECT * FROM users WHERE create_time >= '2024-01-01' AND create_time < '2025-01-01';

-- ❌ 错误：隐式类型转换
SELECT * FROM users WHERE phone = 13800138000;
-- ✅ 正确：字符串比较
SELECT * FROM users WHERE phone = '13800138000';
```

## 四、面试高频题

### Q1: 如何选择索引？

```
A:
1. 高频查询字段
2. 高区分度字段
3. 最左前缀原则
```

### Q2: 如何优化慢查询？

```
A:
1. EXPLAIN分析
2. 添加索引
3. 改写SQL
```

## 五、自测题

1. 解释优化层次
2. 如何使用EXPLAIN？
3. 如何优化慢查询？

---

## 参考文档

- [MySQL Optimizer](https://dev.mysql.com/doc/refman/8.0/en/optimization.html)
- [Explain Output](https://dev.mysql.com/doc/refman/8.0/en/explain-output.html)
