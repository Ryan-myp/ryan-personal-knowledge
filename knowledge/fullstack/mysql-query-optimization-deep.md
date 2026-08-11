# MySQL 查询优化深度实战

> 深入 MySQL 查询优化：慢查询分析、索引优化、执行计划解读。
> 实战案例，包含生产环境问题排查。
> 适用对象：DBA、后端工程师、性能优化工程师

---

## 1. 慢查询分析

### 1.1 开启慢查询日志

```sql
-- 查看慢查询配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;  -- 超过1秒的查询记录

-- 配置日志文件位置
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';
```

### 1.2 分析慢查询

```bash
# 使用 mysqldumpslow 分析
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

# 使用 pt-query-digest 分析
pt-query-digest /var/log/mysql/slow.log

# 使用 mysqldiff 对比
mysqldiff --server1=root:pass@host1 --server2=root:pass@host2
```

---

## 2. 索引优化

### 2.1 最左前缀原则

```sql
-- 联合索引 (a, b, c)
-- 以下查询可以使用索引
SELECT * FROM t WHERE a = 1;
SELECT * FROM t WHERE a = 1 AND b = 2;
SELECT * FROM t WHERE a = 1 AND b = 2 AND c = 3;

-- 以下查询不能使用完整索引
SELECT * FROM t WHERE b = 2;           -- 跳过a
SELECT * FROM t WHERE a = 1 AND c = 3; -- 跳过b
```

### 2.2 索引覆盖

```sql
-- 索引覆盖：只查询索引列
SELECT id, name FROM users WHERE name = 'Alice';
-- 可以直接从索引树获取，无需回表

-- 使用 EXPLAIN 验证
EXPLAIN SELECT id, name FROM users WHERE name = 'Alice';
-- type = ref, Extra = Using index
```

### 2.3 索引下推

```sql
-- MySQL 5.6+ 支持索引下推
-- 在索引层过滤，减少回表次数

EXPLAIN 
SELECT * FROM orders 
WHERE user_id = 100 AND status = 'paid' AND created_at > '2024-01-01';
-- 索引 (user_id, status, created_at)
-- 下推后：先按 user_id 定位，再在索引层过滤 status 和 created_at
```

---

## 3. 执行计划解读

### 3.1 EXPLAIN 输出

```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 100;
```

```
┌─────────────────────────────────────────────────────────────┐
│ id │ select_type │ table  │ type │ possible_keys │ key      │
├─────────────────────────────────────────────────────────────┤
│ 1  │ SIMPLE      │ orders │ ref  │ idx_user_id   │ idx_user │
│    │             │        │      │               │ id       │
├─────────────────────────────────────────────────────────────┤
│ key_len │ ref │ rows │ Extra                         │
├─────────────────────────────────────────────────────────────┤
│ 5       │ const│ 100  │ Using index condition           │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 关键字段说明

| 字段 | 说明 |
|------|------|
| id | 查询标识符 |
| select_type | 查询类型 |
| table | 表名 |
| type | 访问类型 |
| possible_keys | 可能的索引 |
| key | 实际使用的索引 |
| key_len | 索引长度 |
| ref | 索引列引用 |
| rows | 扫描行数 |
| Extra | 额外信息 |

### 3.3 type 访问类型

```
访问类型（从好到坏）：

system > const > eq_ref > ref > range > index > ALL

1. system：表只有一行（系统表）
2. const：主键/唯一索引查询
3. eq_ref：连接查询，唯一索引
4. ref：非唯一索引查询
5. range：索引范围扫描
6. index：全索引扫描
7. all：全表扫描
```

---

## 4. 查询优化实战

### 4.1 分页优化

```sql
-- 低效分页（深度分页）
SELECT * FROM orders LIMIT 100000, 10;
-- 需要扫描100010行，丢弃前100000行

-- 优化方案1：子查询优化
SELECT * FROM orders 
WHERE id >= (SELECT id FROM orders LIMIT 100000, 1)
LIMIT 10;

-- 优化方案2：延迟关联
SELECT o.* FROM orders o
INNER JOIN (SELECT id FROM orders LIMIT 100000, 10) t
ON o.id = t.id;

-- 优化方案3：游标分页
SELECT * FROM orders WHERE id > 100000 LIMIT 10;
```

### 4.2 排序优化

```sql
-- 低效排序（filesort）
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;

-- 创建索引优化排序
CREATE INDEX idx_created_at ON orders(created_at DESC);

-- 使用覆盖索引避免回表
SELECT id, created_at FROM orders ORDER BY created_at DESC LIMIT 10;
```

### 4.3 函数优化

```sql
-- 低效：对索引列使用函数
SELECT * FROM orders WHERE YEAR(created_at) = 2024;

-- 高效：范围查询
SELECT * FROM orders 
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';

-- 低效：字符串函数
SELECT * FROM users WHERE LEFT(phone, 3) = '138';

-- 高效：前缀匹配
SELECT * FROM users WHERE phone LIKE '138%';
```

---

## 5. 表设计优化

### 5.1 数据类型选择

```sql
-- 选择合适的数据类型
TINYINT vs INT:   0-255 用 TINYINT
VARCHAR vs CHAR:  定长用 CHAR，变长用 VARCHAR
DATETIME vs TIMESTAMP: 范围不同，精度不同

-- 示例
CREATE TABLE users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    status TINYINT UNSIGNED NOT NULL DEFAULT 0,  -- 0-255足够
    name VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 5.2 范式设计

```sql
-- 减少冗余，提高一致性
-- 反范式：适当冗余，提高查询性能

-- 示例：订单表冗余用户信息
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    user_name VARCHAR(100),  -- 冗余字段，避免JOIN
    created_at DATETIME
);

-- 使用触发器保持冗余字段一致
DELIMITER //
CREATE TRIGGER update_user_name
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE orders SET user_name = NEW.name WHERE user_id = NEW.id;
END//
DELIMITER ;
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 慢查询 | 日志分析+工具 |
| 索引 | B+树+最左前缀 |
| 执行计划 | EXPLAIN+解读 |
| 优化 | 分页+排序+函数 |

### 6.2 最佳实践

- [ ] 开启慢查询日志
- [ ] 遵循最左前缀原则
- [ ] 使用覆盖索引
- [ ] 避免深度分页
- [ ] 避免索引列函数

---

*最后更新：2026-08-11*
*作者：Ryan*
