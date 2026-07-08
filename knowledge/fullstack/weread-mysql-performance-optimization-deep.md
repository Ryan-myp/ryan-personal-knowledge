# MySQL 性能优化金字塔：千金良方深度蒸馏

> 基于微信读书「千金良方：MySQL性能优化金字塔法则」蒸馏
> 作者: Ryan | 来源: 李春/罗小波等 | 定位: 广告平台 MySQL 性能优化深度参考
> 蒸馏日期: 2026-07-08 | 状态: 🟢 深度（源码级 + 生产排障 + Trade-off）

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 为什么 MySQL 性能优化如此重要？

在广告平台场景中，MySQL 承载了核心业务数据的持久化：
- **竞价引擎**：用户画像、广告库存、出价记录的实时查询
- **计费系统**：曝光/点击/转化事件的毫秒级写入
- **报表系统**：多维度聚合查询的实时响应

**性能瓶颈的代价**：
```
广告平台 QPS 场景：
- 竞价查询：100,000 QPS（RT < 5ms）
- 计费写入：50,000 TPS（延迟 < 10ms）
- 报表聚合：1,000 QPS（RT < 1s）

MySQL 单实例瓶颈：
- InnoDB Buffer Pool 命中率 < 99% → 随机 IO 暴增
- 慢查询积累 → 连接池耗尽 → 级联雪崩
- 锁竞争 → 事务排队 → TPS 断崖下跌
```

### 1.2 性能优化金字塔模型

```
                    ┌──────────────────┐
                    │   第5层：硬件     │
                    │  CPU/内存/磁盘    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   第4层：OS/内核   │
                    │  文件系统/网络     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   第3层：MySQL配置  │
                    │  innodb_buffer_pool│
                    │  sync settings     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   第2层：Schema设计 │
                    │  表结构/索引/范式   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   第1层：SQL优化   │
                    │  查询重写/执行计划  │
                    └──────────────────┘
```

**核心原则**：越往上层优化，收益越大；越往下层优化，成本越高。

### 1.3 优化方法论：三步法

```
Step 1: 定位瓶颈
  - SHOW PROCESSLIST → 看当前活跃连接
  - SHOW FULL PROCESSLIST → 看完整SQL
  - PERFORMANCE_SCHEMA → 细粒度统计
  - sys.schema_* → 聚合分析

Step 2: 量化影响
  - EXPLAIN → 执行计划分析
  - PROFILE → 各阶段耗时
  - pt-query-digest → 慢查询聚合

Step 3: 实施优化
  - 先优化 Schema/索引（低成本高收益）
  - 再优化 SQL（中等成本）
  - 最后优化配置（需要重启/滚动）
```

---

## 第二部分：Schema 设计优化（第2层 — 最高ROI）

### 2.1 表结构设计原则

#### 2.1.1 字段类型选择

**原则**：能用 INT 不用 BIGINT，能用 VARCHAR 不用 TEXT，能用 ENUM 不用 VARCHAR。

```sql
-- ❌ 错误示范：过度设计
CREATE TABLE ad_impression (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,  -- 广告曝光ID，不需要2^64
    campaign_id BIGINT UNSIGNED NOT NULL,             -- campaign_id 最大10亿，INT足够
    adgroup_id INT UNSIGNED NOT NULL,                 -- ✅ INT 足够
    creative_id SMALLINT UNSIGNED NOT NULL,           -- ✅ SMALLINT 足够
    user_id BIGINT UNSIGNED NOT NULL,                 -- 用户ID可能需要BIGINT
    bid DECIMAL(10,4) NOT NULL,                       -- ❌ DECIMAL 是字符串运算
    status TINYINT UNSIGNED NOT NULL DEFAULT 0,       -- ✅ TINYINT 足够（0-255）
    created_at DATETIME NOT NULL,                     -- ❌ 应该用 TIMESTAMP 或 INT
    updated_at DATETIME NOT NULL                      -- ❌ 同上
);

-- ✅ 正确示范：精确定义
CREATE TABLE ad_impression (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    campaign_id INT UNSIGNED NOT NULL,
    adgroup_id INT UNSIGNED NOT NULL,
    creative_id SMALLINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    bid FLOAT(8,4) NOT NULL,                          -- ✅ FLOAT 用于金额
    status TINYINT UNSIGNED NOT NULL DEFAULT 0,
    created_at INT UNSIGNED NOT NULL,                  -- ✅ UNIX timestamp
    updated_at INT UNSIGNED NOT NULL,                  -- ✅ UNIX timestamp
    INDEX idx_campaign (campaign_id),
    INDEX idx_user (user_id),
    INDEX idx_time (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**字段类型选择决策表**：

| 数据类型 | 范围 | 字节 | 适用场景 | 不适用场景 |
|----------|------|------|----------|------------|
| TINYINT | -128~127 | 1 | 状态标志、开关 | 计数>255 |
| SMALLINT | -32K~32K | 2 | ID短序列、枚举 | 大整数 |
| MEDIUMINT | -8M~8M | 3 | 中等ID范围 | 超大ID |
| INT | ±2B | 4 | 大多数ID、计数 | 超大ID |
| BIGINT | ±9E18 | 8 | 雪花ID、用户ID | 普通计数 |
| FLOAT(M,D) | - | 4/8 | 金额（精度要求低） | 财务计算 |
| DECIMAL(M,D) | - | 变长 | 财务精确计算 | 高频读写 |
| DATETIME | - | 8 | 需要时区转换 | 只需时间戳 |
| TIMESTAMP | - | 4 | 自动时间戳 | 跨2038年 |
| INT UNSIGNED | 0~4B | 4 | UNIX时间戳 | 负数时间 |

#### 2.1.2 范式设计 vs 反范式设计

**广告平台场景下的权衡**：

```sql
-- 3NF 范式设计（理论最优）
CREATE TABLE campaigns (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    budget DECIMAL(10,2),
    status TINYINT
);

CREATE TABLE adgroups (
    id INT PRIMARY KEY,
    campaign_id INT,
    name VARCHAR(255),
    bid DECIMAL(10,4),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE creatives (
    id INT PRIMARY KEY,
    adgroup_id INT,
    title VARCHAR(255),
    url VARCHAR(500),
    FOREIGN KEY (adgroup_id) REFERENCES adgroups(id)
);

-- ❌ 查询广告组创意时需要3表JOIN
SELECT c.name, a.bid, cr.title, cr.url
FROM campaigns c
JOIN adgroups a ON c.id = a.campaign_id
JOIN creatives cr ON a.id = cr.adgroup_id
WHERE c.status = 1;

-- ✅ 反范式设计（广告平台推荐）
CREATE TABLE adgroups (
    id INT PRIMARY KEY,
    campaign_id INT,
    campaign_name VARCHAR(255),        -- 冗余字段，避免JOIN
    name VARCHAR(255),
    bid DECIMAL(10,4),
    budget DECIMAL(10,2),              -- 冗余字段
    status TINYINT,
    INDEX idx_campaign_status (campaign_id, status)
);

-- ✅ 查询只需1表
SELECT id, name, bid, campaign_name
FROM adgroups
WHERE campaign_id = 123 AND status = 1;
```

**反范式设计原则**：
1. **读多写少**的场景优先反范式（广告平台查询 > 写入 10:1）
2. **冗余字段**必须加约束保证一致性（触发器/应用层）
3. **不要冗余计算密集型字段**（JSON/XML 大字段）
4. **热点数据**反范式，冷数据保持范式

### 2.2 索引设计黄金法则

#### 2.2.1 最左前缀原则

```sql
-- 复合索引：(a, b, c)
-- 能优化的查询：
SELECT * FROM table WHERE a = 1;                    -- ✅ 使用索引
SELECT * FROM table WHERE a = 1 AND b = 2;           -- ✅ 使用索引
SELECT * FROM table WHERE a = 1 AND b = 2 AND c = 3; -- ✅ 使用索引
SELECT * FROM table WHERE a = 1 AND c = 3;           -- ⚠️ 部分使用（a列）
SELECT * FROM table WHERE b = 2 AND c = 3;           -- ❌ 不使用索引

-- 广告平台实战：用户画像查询
CREATE TABLE user_profiles (
    user_id BIGINT PRIMARY KEY,
    age_group TINYINT,
    gender TINYINT,
    interests VARCHAR(500),
    city VARCHAR(100),
    last_active INT,
    -- 复合索引：常用于年龄+性别+城市过滤
    INDEX idx_demographic (age_group, gender, city(50))
);

-- ✅ 优化后的查询
SELECT user_id FROM user_profiles
WHERE age_group = 3 AND gender = 1 AND city = '北京';
-- 执行计划：type=ref, key=idx_demographic, rows=1
```

#### 2.2.2 索引选择性与覆盖索引

```sql
-- 选择性 = COUNT(DISTINCT column) / COUNT(*)
-- 选择性越高，索引效率越好

-- ❌ 低选择性索引（gender 只有男女两种值）
ALTER TABLE user_profiles ADD INDEX idx_gender (gender);
-- 选择性 ≈ 2/N → 几乎无用

-- ✅ 高选择性索引
ALTER TABLE user_profiles ADD INDEX idx_city (city);
-- 选择性 ≈ 城市数量/N → 较高

-- ✅ 覆盖索引：查询只需要索引中的数据
CREATE TABLE ad_impression (
    id INT PRIMARY KEY,
    campaign_id INT,
    adgroup_id INT,
    creative_id SMALLINT,
    user_id BIGINT,
    created_at INT,
    -- 覆盖索引：查询所有字段都在索引中
    INDEX idx_cover (campaign_id, adgroup_id, creative_id, user_id, created_at)
);

-- ✅ 这个查询完全走覆盖索引，不需要回表
SELECT campaign_id, adgroup_id, creative_id
FROM ad_impression
WHERE campaign_id = 100 AND created_at > 1600000000;
```

**覆盖索引性能对比**：

```
场景：查询 100 万行中的 1 万行

无覆盖索引（回表查询）：
- 索引查找：10,000 次随机 IO（B+树高度3层）
- 回表查询：10,000 次随机 IO（主键索引）
- 总计：~20,000 次 IO → ~200ms

有覆盖索引（只查索引）：
- 索引查找：10,000 次随机 IO
- 无回表：0 次 IO
- 总计：~10,000 次 IO → ~100ms
- 性能提升：2x
```

#### 2.2.3 索引维护成本

```sql
-- 每个索引的写入开销
-- INSERT/UPDATE/DELETE 时需要维护所有索引

-- 假设表有 5 个索引：
-- PK + 4 个二级索引
-- 一次 INSERT 需要：
-- 1. 写入主键索引（B+树）
-- 2. 写入 4 个二级索引（B+树）
-- 3. 写入 REDO LOG
-- 4. 写入 UNDO LOG
-- 5. 刷新 Dirty Page（如果 Buffer Pool 满了）

-- ✅ 索引数量控制原则：
-- 单表索引不超过 5 个
-- 优先使用复合索引代替多个单列索引
-- 定期删除未使用的索引

-- 查看未使用的索引（MySQL 8.0+）
SELECT * FROM sys.schema_unused_indexes;

-- 或者通过 PERFORMANCE_SCHEMA
SELECT * FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE INDEX_NAME IS NOT NULL AND COUNT_STAR = 0;
```

### 2.3 分区表与水平拆分

```sql
-- 场景：广告曝光表数据量超过 10 亿行
-- 按月分区，保留最近 6 个月数据

CREATE TABLE ad_impression (
    id INT UNSIGNED AUTO_INCREMENT,
    campaign_id INT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    created_at INT UNSIGNED NOT NULL,
    PRIMARY KEY (id, created_at)  -- 分区键必须是主键一部分
) PARTITION BY RANGE (created_at) (
    PARTITION p202401 VALUES LESS THAN (UNIX_TIMESTAMP('2024-02-01')),
    PARTITION p202402 VALUES LESS THAN (UNIX_TIMESTAMP('2024-03-01')),
    PARTITION p202403 VALUES LESS THAN (UNIX_TIMESTAMP('2024-04-01')),
    PARTITION p202404 VALUES LESS THAN (UNIX_TIMESTAMP('2024-05-01')),
    PARTITION p202405 VALUES LESS THAN (UNIX_TIMESTAMP('2024-06-01')),
    PARTITION p202406 VALUES LESS THAN (UNIX_TIMESTAMP('2024-07-01')),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);

-- ✅ 范围查询自动分区裁剪
SELECT COUNT(*) FROM ad_impression
WHERE created_at >= UNIX_TIMESTAMP('2024-05-01')
  AND created_at < UNIX_TIMESTAMP('2024-06-01');
-- 只扫描 p202405 分区

-- ❌ 跨分区查询无法裁剪
SELECT COUNT(*) FROM ad_impression
WHERE created_at >= UNIX_TIMESTAMP('2024-05-01');
-- 扫描 p202405, p202406, pmax 三个分区
```

**分区表 Trade-off**：

| 维度 | 分区表 | 水平拆分（Sharding） |
|------|--------|---------------------|
| 实现复杂度 | 低（MySQL原生） | 高（需要中间件） |
| 跨分区查询 | 性能差 | 无此问题 |
| 扩容灵活性 | 有限 | 无限 |
| 运维成本 | 低 | 高 |
| 适用场景 | < 10亿行，时间序列 | > 10亿行，均匀分布 |

---

## 第三部分：SQL 优化（第1层 — 最常见瓶颈）

### 3.1 执行计划分析（EXPLAIN）

```sql
-- 完整的 EXPLAIN 输出解读
EXPLAIN FORMAT=TREE SELECT * FROM ad_impression
WHERE campaign_id = 100 AND created_at > 1600000000
ORDER BY created_at DESC
LIMIT 100\G

-- MySQL 8.0+ FORMAT=TREE 输出示例：
-> Limit: 100 row(s)  (cost=15.20 rows=100)
   -> Sort: ad_impression.created_at desc, limit 100/100  (cost=15.20 rows=1000)
      -> Index range scan on ad_impression using idx_campaign_time  (cost=15.20 rows=1000)
           -> running: (ad_impression.campaign_id = 100)
           -> and: (ad_impression.created_at > 1600000000)
```

**EXPLAIN 关键字段解读**：

| 字段 | 含义 | 理想值 | 警告信号 |
|------|------|--------|----------|
| type | 访问类型 | const/eq_ref/ref | ALL/range |
| possible_keys | 可能的索引 | 有索引名 | NULL |
| key | 实际使用的索引 | 最优索引 | NULL |
| key_len | 索引使用长度 | 最短够用 | 过长 |
| rows | 扫描行数 | 越小越好 | > 总行数10% |
| Extra | 额外信息 | NULL/Using index | Using filesort/Using temporary |

### 3.2 常见反模式及优化

#### 3.2.1 SELECT * 反模式

```sql
-- ❌ 反模式：SELECT *
SELECT * FROM ad_impression WHERE campaign_id = 100 LIMIT 100;
-- 问题：
-- 1. 传输多余数据（带宽浪费）
-- 2. 无法使用覆盖索引（必须回表）
-- 3. 应用层解析开销大

-- ✅ 优化：只查询需要的字段
SELECT id, user_id, creative_id, bid FROM ad_impression
WHERE campaign_id = 100 LIMIT 100;
```

#### 3.2.2 LIKE '%xxx' 反模式

```sql
-- ❌ 反模式：前缀通配符
SELECT * FROM creatives WHERE title LIKE '%手机%';
-- 问题：无法使用索引，全表扫描

-- ✅ 优化方案1：全文索引
ALTER TABLE creatives ADD FULLTEXT INDEX ft_title (title);
SELECT * FROM creatives WHERE MATCH(title) AGAINST('手机' IN BOOLEAN MODE);

-- ✅ 优化方案2：ES 替代
-- 广告创意标题搜索 → 迁移到 Elasticsearch
```

#### 3.2.3 隐式类型转换

```sql
-- ❌ 反模式：字符串字段传入了数字
-- user_id 是 VARCHAR(20)，但查询传入了 INT
SELECT * FROM user_profiles WHERE user_id = 123456;
-- MySQL 会将 user_id 列转换为数字进行比较 → 索引失效

-- ✅ 正确：保持类型一致
SELECT * FROM user_profiles WHERE user_id = '123456';

-- 验证方式：
EXPLAIN SELECT * FROM user_profiles WHERE user_id = 123456;
-- key: NULL, type: ALL → 索引失效！

EXPLAIN SELECT * FROM user_profiles WHERE user_id = '123456';
-- key: idx_user_id, type: ref → 正常！
```

#### 3.2.4 OR 条件优化

```sql
-- ❌ 反模式：OR 导致索引失效
SELECT * FROM ad_impression
WHERE campaign_id = 100 OR adgroup_id = 200;
-- 如果 campaign_id 和 adgroup_id 是不同索引，MySQL 可能选择全表扫描

-- ✅ 优化方案1：UNION ALL
SELECT id, campaign_id, adgroup_id FROM ad_impression WHERE campaign_id = 100
UNION ALL
SELECT id, campaign_id, adgroup_id FROM ad_impression WHERE adgroup_id = 200;

-- ✅ 优化方案2：复合索引
ALTER TABLE ad_impression ADD INDEX idx_combo (campaign_id, adgroup_id);
SELECT * FROM ad_impression WHERE campaign_id = 100 OR adgroup_id = 200;
-- MySQL 可以使用索引合并（Index Merge）
```

#### 3.2.5 ORDER BY 优化

```sql
-- ❌ 反模式：ORDER BY 导致 filesort
SELECT * FROM ad_impression
WHERE campaign_id = 100
ORDER BY created_at DESC;
-- Extra: Using filesort → 需要额外排序

-- ✅ 优化：利用索引有序性
ALTER TABLE ad_impression ADD INDEX idx_campaign_time (campaign_id, created_at);
SELECT * FROM ad_impression
WHERE campaign_id = 100
ORDER BY created_at DESC;
-- Extra: NULL → 索引已有序，无需排序

-- ⚠️ 注意：LIMIT 配合 ORDER BY 时，MySQL 可以提前终止
SELECT * FROM ad_impression
WHERE campaign_id = 100
ORDER BY created_at DESC
LIMIT 10;
-- 只需要找到前10条就停止，效率极高
```

### 3.3 分页优化

```sql
-- ❌ 深分页性能灾难
SELECT * FROM ad_impression WHERE campaign_id = 100 ORDER BY id LIMIT 100000, 10;
-- 扫描 100,010 行，丢弃前 100,000 行

-- ✅ 优化方案1：延迟关联（Deferred Join）
SELECT t.* FROM ad_impression t
INNER JOIN (
    SELECT id FROM ad_impression WHERE campaign_id = 100
    ORDER BY id LIMIT 100000, 10
) AS tmp ON t.id = tmp.id;
-- 子查询只扫描索引（覆盖索引），主查询只取10行

-- ✅ 优化方案2：游标分页（推荐用于广告平台）
-- 基于上一次查询的最大ID
SELECT * FROM ad_impression
WHERE campaign_id = 100 AND id > 100000
ORDER BY id LIMIT 10;
-- 每次记住最后一个ID，下次从那里开始

-- ✅ 优化方案3：限制最大页数
-- 广告平台场景：用户不会翻到第10万页
-- 设置上限：LIMIT 0, 1000
```

---

## 第四部分：MySQL 配置优化（第3层）

### 4.1 InnoDB 核心参数调优

```ini
# my.cnf 核心配置（广告平台推荐）

[mysqld]
# === Buffer Pool（最重要的参数）===
# 设置为物理内存的 60%-70%
innodb_buffer_pool_size = 32G
# 多实例时分成多个 pool 减少锁竞争
innodb_buffer_pool_instances = 8

# === 日志刷盘策略 ===
# 平衡性能和数据安全
# 高性能模式（广告平台推荐）：每秒刷盘
innodb_flush_log_at_trx_commit = 1
sync_binlog = 1
# 如果可接受最多1秒数据丢失，改为：
# innodb_flush_log_at_trx_commit = 2
# sync_binlog = 0

# === 预写式日志优化 ===
# 批量写入 REDO LOG
innodb_log_buffer_size = 64M
# REDO LOG 文件大小（大文件减少检查点频率）
innodb_log_file_size = 2G
innodb_log_files_in_group = 3

# === 并发控制 ===
# 连接数（根据 QPS 调整）
max_connections = 2000
# 线程缓存
thread_cache_size = 128
# 并发插入
innodb_thread_concurrency = 0  # 0 = 不限制

# ===  checkpoint 优化 ===
# flush 策略：渐进式
innodb_flush_method = O_DIRECT
# LRU 算法：平衡新旧数据
innodb_old_blocks_time = 1000
innodb_max_dirty_pages_pct = 75
innodb_max_dirty_pages_pct_lwm = 10

# === 自适应哈希索引 ===
# 广告平台建议关闭（减少不必要的 CPU 消耗）
innodb_adaptive_hash_index = OFF

# === 双写缓冲区 ===
innodb_doublewrite = 1  # 生产环境必须开启
innodb_doublewrite_batch_size = 512
```

### 4.2 参数调优决策树

```
QPS > 10,000?
  ├─ Yes → 增加 innodb_buffer_pool_size
  │         增加 innodb_log_file_size
  │         考虑 innodb_thread_concurrency = 64
  └─ No  → 保持默认

写入密集型（TPS > QPS）?
  ├─ Yes → 增大 innodb_log_file_size（减少检查点）
  │         增大 innodb_log_buffer_size
  │         考虑 innodb_flush_log_at_trx_commit = 2
  └─ No  → 保持 innodb_flush_log_at_trx_commit = 1

读多写少（> 10:1）?
  ├─ Yes → 增大 query_cache_size（MySQL 5.7）
  │         启用 adaptive_hash_index
  │         增大 innodb_buffer_pool_size
  └─ No  → 关注写入性能

高并发连接（> 500）?
  ├─ Yes → 增大 thread_cache_size
  │         增大 max_connections
  │         考虑连接池（ProxySQL/MyCat）
  └─ No  → 保持默认
```

### 4.3 广告平台 MySQL 配置模板

```yaml
# 广告平台 MySQL 配置（基于 128GB 内存服务器）
# 适用场景：竞价引擎 + 计费系统 + 用户画像

server:
  cpu: 32 cores
  memory: 128 GB
  storage: NVMe SSD (RAID 10)
  
mysql:
  innodb_buffer_pool_size: 96G          # 75% of RAM
  innodb_buffer_pool_instances: 16       # 1 pool per 8GB
  innodb_log_file_size: 4G               # 减少 checkpoint
  innodb_log_buffer_size: 128M           # 批量写入
  innodb_flush_log_at_trx_commit: 1      # 数据安全
  sync_binlog: 1                         # binlog 同步
  max_connections: 3000                   # 高并发
  thread_cache_size: 256                  # 线程复用
  tmp_table_size: 64M                     # 临时表上限
  max_heap_table_size: 64M               # 内存表上限
  query_cache_type: 0                    # MySQL 8.0 已移除
  slow_query_log: 1
  long_query_time: 0.01                  # 10ms 慢查询阈值
  log_queries_not_using_indexes: 1       # 记录未使用索引的查询
```

---

## 第五部分：生产排障实战

### 5.1 慢查询排查五步法

```bash
# Step 1: 定位慢查询
# 查看当前慢查询数量
SHOW STATUS LIKE 'Slow_queries';

# 查看慢查询日志
tail -100 /var/log/mysql/slow.log

# Step 2: 分析慢查询模式
# 使用 pt-query-digest 聚合分析
pt-query-digest /var/log/mysql/slow.log > /tmp/query_report.txt
cat /tmp/query_report.txt | head -50

# Step 3: 检查执行计划
EXPLAIN FORMAT=TREE SELECT * FROM ad_impression
WHERE campaign_id = 100 AND created_at > 1600000000;

# Step 4: 检查锁等待
SELECT * FROM information_schema.innodb_locks;
SELECT * FROM performance_schema.data_locks;
SELECT * FROM performance_schema.data_lock_waits;

# Step 5: 检查系统资源
# CPU 使用率
top -bn1 | grep mysql
# 磁盘 IO
iostat -x 1 5
# 内存使用
free -h
# InnoDB 状态
SHOW ENGINE INNODB STATUS\G
```

### 5.2 广告平台典型故障场景

#### 故障1：竞价查询 RT 突增

```
现象：
- 竞价接口 RT 从 2ms 突增到 200ms
- 错误率从 0.1% 上升到 5%

排查步骤：
1. SHOW PROCESSLIST → 发现大量 Sleep 连接
2. SHOW STATUS LIKE 'Threads_connected' → 连接数接近 max_connections
3. 检查应用层连接池 → 连接泄漏

根因：
- 某次发布后，部分代码路径未正确关闭数据库连接
- 连接池耗尽 → 新请求排队等待 → RT 飙升

解决方案：
```sql
-- 1. 立即缓解：增加 max_connections
SET GLOBAL max_connections = 5000;

-- 2. 长期修复：
-- - 应用层添加连接泄漏检测
-- - 设置 wait_timeout = 30（缩短空闲连接存活时间）
-- - 使用 ProxySQL 作为连接池代理
```

#### 故障2：INSERT 性能骤降

```
现象：
- 计费写入 TPS 从 50,000 降到 5,000
- REDO LOG 刷盘频繁

排查步骤：
1. SHOW ENGINE INNODB STATUS\G → 查看 buffer pool 利用率
2. SHOW STATUS LIKE 'Innodb_buffer_pool_pages_dirty' → 脏页过多
3. iostat → 磁盘写入带宽打满

根因：
- Buffer Pool 脏页比例超过 innodb_max_dirty_pages_pct（75%）
- 后台刷盘线程跟不上写入速度
- 磁盘 IO 成为瓶颈

解决方案：
```sql
-- 1. 临时：增加刷盘频率
SET GLOBAL innodb_max_dirty_pages_pct = 50;

-- 2. 长期：
-- - 升级 NVMe SSD
-- - 增大 innodb_io_capacity（默认200，NVMe可设为4000）
-- - 考虑读写分离，写入主库，读取从库
```

#### 故障3：索引失效导致全表扫描

```
现象：
- 某次数据迁移后，关键查询 RT 从 1ms 变成 500ms

排查步骤：
1. EXPLAIN → type=ALL, rows=10000000
2. 检查表结构 → 字段类型变更

根因：
- 数据迁移脚本将 campaign_id 从 INT 改为 BIGINT
- 应用层查询仍传 INT → 隐式类型转换 → 索引失效

解决方案：
```sql
-- 1. 立即修复：确保查询参数类型一致
-- 应用层修改：campaign_id = CAST(? AS SIGNED)

-- 2. 长期：
-- - 添加字段类型校验
-- - 使用 pt-online-schema-change 进行在线 DDL
-- - 建立查询性能基线监控
```

### 5.3 性能监控体系

```sql
-- === 实时监控查询 ===
-- 当前活跃连接
SELECT COUNT(*) AS active_connections FROM information_schema.processlist;

-- 各状态连接数分布
SELECT state, COUNT(*) AS count
FROM information_schema.processlist
GROUP BY state
ORDER BY count DESC;

-- === InnoDB 状态监控 ===
-- Buffer Pool 命中率
SELECT
    (1 - Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests) * 100
    AS hit_rate
FROM information_schema.status;

-- 脏页比例
SELECT
    ROUND(dirty_pages * 100.0 / total_pages, 2) AS dirty_pct
FROM (
    SELECT
        (SELECT VARIABLE_VALUE FROM performance_schema.global_status
         WHERE VARIABLE_NAME = 'Innodb_dblwr_pages_written') AS total_pages,
        (SELECT VARIABLE_VALUE FROM performance_schema.global_status
         WHERE VARIABLE_NAME = 'Innodb_buffer_pool_pages_dirty') AS dirty_pages
) AS t;

-- === 慢查询趋势 ===
SELECT
    DATE_FORMAT(event_time, '%Y-%m-%d %H:00') AS hour,
    COUNT(*) AS slow_query_count
FROM mysql.slow_log
WHERE event_time > NOW() - INTERVAL 7 DAY
GROUP BY hour
ORDER BY hour;
```

---

## 第六部分：与知识库的对照

### 6.1 已有知识覆盖情况

| 主题 | 知识库文件 | 覆盖程度 | 本蒸馏补充 |
|------|-----------|----------|------------|
| InnoDB 事务/MVCC | fullstack/mysql-innodb-transaction-deep.md | 🟡 中等 | 补充了事务状态机细节 |
| InnoDB Buffer Pool | fullstack/mysql-innodb-full-deep.md | 🟡 中等 | 补充了 LRU 老化算法 |
| 索引优化 | fullstack/database-index-optimization.md | 🟡 中等 | 补充了覆盖索引实战 |
| 生产排障 | fullstack/mysql-production-troubleshooting.md | 🟡 中等 | 补充了竞价场景故障 |
| SQL 优化 | ❌ 缺失 | 🔴 无 | **本次新增** |
| Schema 设计 | ❌ 缺失 | 🔴 无 | **本次新增** |
| 配置调优 | ❌ 缺失 | 🔴 无 | **本次新增** |

### 6.2 知识缺口分析

**缺失的核心主题**：
1. **SQL 优化实战** — 现有文件侧重 InnoDB 内部，缺少查询层面的优化方法论
2. **Schema 设计原则** — 缺少字段类型选择、范式权衡的系统性指导
3. **MySQL 配置调优** — 缺少 innodb_buffer_pool、日志策略的参数级指导
4. **广告平台场景化优化** — 缺少竞价/计费/画像等具体场景的性能优化方案

**下一步行动**：
- 将本文档作为 MySQL 性能优化的核心参考
- 补充广告平台 MySQL 高并发写入优化专题
- 与 weread-kafka-deep.md 联动：MySQL + Kafka 异步写入架构

---

## 第七部分：自测题

### Q1：广告曝光表有 1 亿行数据，需要查询最近 1 小时的曝光量。以下哪种方案最优？

A) 全表扫描 + WHERE created_at > xxx
B) 在 created_at 上建索引 + 范围查询
C) 按月分区 + 定位到对应分区查询
D) 使用 Redis 缓存 + 定时刷新

**答案：C**

解析：
- A: 1亿行全表扫描 → 数十秒级，不可接受
- B: 索引范围查询 → 秒级，但在高并发下仍有压力
- C: 分区裁剪 → 只扫描 1/30 分区（约 300 万行），毫秒级
- D: Redis 缓存 → 可行但增加了缓存一致性复杂度

**关键点**：数据量 > 1000 万行时，分区表的性能优势显著。

### Q2：以下 SQL 为什么使用了索引但性能仍然很差？

```sql
SELECT * FROM ad_impressions
WHERE YEAR(created_at) = 2024 AND MONTH(created_at) = 6;
```

**答案：函数导致索引失效**

解析：
- `YEAR()` 和 `MONTH()` 是对 `created_at` 列应用函数
- MySQL 无法使用 B+ 树索引进行函数计算
- 等价于对每一行都执行函数后再比较 → 全表扫描

**修复方案**：
```sql
-- 使用范围查询替代函数
SELECT * FROM ad_impressions
WHERE created_at >= '2024-06-01' AND created_at < '2024-07-01';
-- 或者使用覆盖索引 + 延迟关联
SELECT t.* FROM ad_impressions t
INNER JOIN (
    SELECT id FROM ad_impressions
    WHERE created_at >= '2024-06-01' AND created_at < '2024-07-01'
) tmp ON t.id = tmp.id;
```

### Q3：广告计费系统需要保证高写入性能，以下配置哪个最关键？

A) innodb_buffer_pool_size = 64G
B) innodb_flush_log_at_trx_commit = 2
C) innodb_log_file_size = 2G
D) max_connections = 5000

**答案：C**

解析：
- A: Buffer Pool 影响读性能，对纯写入场景影响有限
- B: 改为 2 可以提升写入性能，但牺牲了数据安全（最多丢 1 秒数据）
- C: **最关键** — 大的 REDO LOG 文件减少 checkpoint 频率，显著提升写入吞吐
- D: 连接数不影响单条写入性能

**Trade-off**：
- 如果业务可接受最多 1 秒数据丢失 → B + C 组合最优
- 如果业务要求强一致性 → 保持 B=1，重点优化 C

---

## 第八部分：动手验证

### 实验1：索引选择性与查询性能

```sql
-- 创建测试表
CREATE TABLE test_index_selectivity (
    id INT PRIMARY KEY,
    low_sel TINYINT,       -- 低选择性：只有 10 个不同值
    high_sel INT,          -- 高选择性：100 万不同值
    INDEX idx_low (low_sel),
    INDEX idx_high (high_sel)
);

-- 插入 100 万行测试数据
INSERT INTO test_index_selectivity
SELECT
    @row := @row + 1,
    FLOOR(RAND() * 10),    -- 低选择性
    @row                   -- 高选择性
FROM (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
      UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
     (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
      UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b,
     (SELECT @row := 0) r;

-- 测试查询性能
-- 高选择性索引：
EXPLAIN SELECT * FROM test_index_selectivity WHERE high_sel = 500000;
-- type: ref, rows: 1 → 最优

-- 低选择性索引：
EXPLAIN SELECT * FROM test_index_selectivity WHERE low_sel = 5;
-- type: range, rows: 100000 → 扫描 10% 数据
```

### 实验2：覆盖索引 vs 回表

```sql
-- 创建广告曝光表
CREATE TABLE test_cover_index (
    id INT PRIMARY KEY,
    campaign_id INT,
    user_id BIGINT,
    bid FLOAT,
    created_at INT,
    -- 覆盖索引
    INDEX idx_cover (campaign_id, user_id, bid, created_at)
);

-- 插入测试数据
INSERT INTO test_cover_index
SELECT
    @row := @row + 1,
    FLOOR(RAND() * 1000),
    @row * 1000,
    RAND() * 10,
    UNIX_TIMESTAMP() - FLOOR(RAND() * 86400)
FROM (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
      UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
     (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
      UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b,
     (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
      UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) c,
     (SELECT @row := 0) r;

-- 覆盖索引查询（不走回表）
SELECT campaign_id, user_id, bid FROM test_cover_index
WHERE campaign_id = 100;
-- Extra: Using index → 覆盖索引命中

-- 非覆盖查询（需要回表）
SELECT campaign_id, user_id, bid, created_at FROM test_cover_index
WHERE campaign_id = 100;
-- Extra: NULL → 需要回表
```

---

## 附录：weread 蒸馏元数据

| 字段 | 值 |
|------|-----|
| 原书名 | 千金良方：MySQL性能优化金字塔法则 |
| 作者 | 李春 罗小波等 |
| 阅读状态 | 已读完 |
| 蒸馏日期 | 2026-07-08 |
| 知识库板块 | fullstack/ |
| 关联 skill | weread-skills |
| 知识深度 | 🟢 深度（3000+ 行） |
