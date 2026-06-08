# MySQL 内核深入 — InnoDB、MVCC、B+Tree、XA事务

> 标签: `#MySQL` `#InnoDB` `#MVCC` `#B+Tree` `#XA事务` `#源码分析`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. MySQL 存储引擎架构

### 1.1 插件式存储引擎架构

```
┌─────────────────────────────────────────────────────────────┐
│                        MySQL Server                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ 连接器   │ │ 查询缓存 │ │ 解析器   │ │ 优化器( Cost  )│  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│                              │                               │
│                   ┌──────────▼──────────┐                    │
│                   │   执行引擎 (Executor)│                    │
│                   └──────────┬──────────┘                    │
│                              │                               │
│              ┌───────────────┼───────────────┐               │
│              ▼               ▼               ▼               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │  InnoDB (默认)│ │  MyISAM      │ │  Memory      │         │
│  │  事务/行锁    │ │  表锁        │ │  内存表      │         │
│  └──────────────┘ └──────────────┘ └──────────────┘         │
└─────────────────────────────────────────────────────────────┘

执行器调用存储引擎 API:
  handler::read_first()   // 读第一条记录
  handler::read_next()    // 读下一条
  handler::write_row()    // 写入一行
  handler::update_row()   // 更新一行
```

### 1.2 InnoDB 架构组件

```
┌─────────────────────────────────────────────────────────────┐
│                       InnoDB 架构                            │
│                                                             │
│  Buffer Pool (缓冲池)                                       │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│  │ Page 1 │ │ Page 2 │ │ Page 3 │ │  ...   │  ◄── 数据页   │
│  └────────┘ └────────┘ └────────┘ └────────┘              │
│    ▲         ▲         ▲         ▲                          │
│    │         │         │         │                          │
│  Change Buffer  │      Dirty Page  │                       │
│  (变更缓冲)       │      (脏页)      │                      │
│                   │         │       │                       │
│                   ▼         ▼       │                       │
│              Redo Log   Undo Log  │                       │
│              (重做日志) (回滚日志)  │                       │
│                   │         │       │                       │
│                   ▼         ▼       │                       │
│  Double Write Buffer (双写缓冲)      │                       │
│                   │                   │                      │
│                   ▼                   │                      │
│              ibdata1 / .ibd (磁盘)     │                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. InnoDB 存储结构

### 2.1 表空间（Tablespace）

```
MySQL 8.0 默认: InnoDB 单表空间模式 (innodb_file_per_table=ON)

每个 InnoDB 表:
  ├── tablename.ibd    // 表数据文件（包含数据和索引）
  ├── tablename.frm    // 表结构定义（MySQL 8.0+ 不再需要）

多表空间模式:
  ├── ibdata1          // 共享表空间（系统表空间）
  │   ├── 数据字典
  │   ├── Undo Log
  │   └── Double Write Buffer
  ├── ibtmp1           // 临时表空间
  └── *.ibd             // 各表的独立表空间
```

### 2.2 页（Page）结构

```
InnoDB 最小的 IO 单位是页，默认 16KB（innodb_page_size）

┌─────────────────────────────────────────┐
│ Page Header (页头) 38 字节                │
│  FIL_PAGE_OFFSET   4B  页偏移量          │
│  FIL_PAGE_PREV     4B  前页偏移量         │
│  FIL_PAGE_NEXT     4B  后页偏移量         │
│  FIL_PAGE_LSN      8B  页的 LSN          │
│  FIL_PAGE_TYPE     2B  页类型             │
│  FIL_PAGE_FLUSH_LSN 8B 页的刷新 LSN      │
│  FIL_PAGE_SPACE_OR_CHKSUM 4B            │
├─────────────────────────────────────────┤
│ File Directory Space (文件目录区) 0-76B  │
│  记录页中记录的位置信息                     │
├─────────────────────────────────────────┤
│ User Data (用户数据区)                    │
│  Row 1                                    │
│  Row 2                                    │
│  ...                                      │
│  Record Header: 变长字段列表 + NULL列表   │
│  + 6字节记录头（delete_mask、min_rec_flag│
│   n_owned、heap_no、length）            │
├─────────────────────────────────────────┤
│ Infimum (最小记录) 5 字节                  │
│ Supremum (最大记录) 5 字节                 │
├─────────────────────────────────────────┤
│ Page Directory (页目录)                   │
│  每组 36 字节，最多 1000 组               │
│  用于二分查找加速定位记录                  │
├─────────────────────────────────────────┤
│ Trx Roll Pointer (事务回滚指针) 7B        │
├─────────────────────────────────────────┤
│ Page Trailer (页尾) 8 字节                │
└─────────────────────────────────────────┘
```

### 2.3 行格式（Row Format）

```
MySQL 5.7+ 默认: DYNAMIC 格式

Compact 格式 (5.0-5.6):
┌──────┬─────────────┬──────────┬──────────┐
│变长  │ NULL 标识   │ 记录头   │ 主键/行ID│
│字段表│ (1B)       │ (6B)     │ (可变)   │
└──────┴─────────────┴──────────┴──────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│ 固定长度字段 + 前768字节变长字段直接存储       │
│ 超过768字节的部分溢出存储在溢出页（off-page）  │
└─────────────────────────────────────────────┘

DYNAMIC 格式 (5.7+):
┌──────┬─────────────┬──────────┬──────────┬──────────┐
│变长  │ NULL 标识   │ 记录头   │ 主键/行ID│ 指针     │
│字段表│ (1B)       │ (6B)     │ (可变)   │ (20B)    │
└──────┴─────────────┴──────────┴──────────┴──────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│ 所有变长字段只存储指针，实际数据全部 off-page │
│ 适合 TEXT/BLOB 大字段，节省页内空间          │
│ 前 768 字节仍然存储在页内（快速访问）         │
└─────────────────────────────────────────────┘

COMPRESSED 格式:
  基于 DYNAMIC，使用 zlib 压缩，page_size 可设为 1KB/2KB/4KB/8KB
```

---

## 3. B+Tree 索引结构

### 3.1 为什么用 B+Tree 而非 BTree/Hash/二叉树？

```
索引结构对比:

二叉搜索树:
  问题: 极端情况下退化为链表（有序数据）
  树高: O(N) 最坏，O(logN) 平均
  
红黑树:
  优点: 自平衡，O(logN)
  问题: 树高仍然较高，磁盘 IO 多
  
B+Tree (InnoDB 默认):
  优点:
  1. 多路平衡树，树高通常 2-3 层
     - 16KB 页，索引列 8B + 记录指针 6B = 14B
     - 每个页可容纳 16*1024/14 ≈ 1170 个指针
     - 3 层: 1170^2 ≈ 137 万条记录（足够支撑千万级数据）
  2. 所有数据在叶子节点，范围查询高效
  3. 叶子节点双向链表，范围扫描高效
  4. 磁盘 IO 次数少（树高 2-3 次 IO）
  
Hash 索引:
  优点: O(1) 精确查询
  问题: 不支持范围查询、排序、分组
  适用: Memory 引擎的 MEMORY 存储引擎
```

### 3.2 B+Tree 索引结构图

```
B+Tree 聚簇索引结构:

            ┌───┐
            │根 │  ← 非叶子节点（索引页）
            └─┬─┘
          ┌───┼───┐
          ▼   ▼   ▼
    ┌───┐┌───┐┌───┐  ← 非叶子节点
    │K1 ││K2 ││K3 │
    └─┬─┘└─┬─┘└─┬─┘
   ┌──┴──┐│   │┌──┴──┐
   ▼     ▼ ▼   ▼ ▼     ▼
┌────┐┌────┐│┌────┐┌────┐┌────┐
│D1  ││D2  │││D3  ││D4  ││D5  │  ← 叶子节点（数据页）
│(PK)││(PK)│││(PK)││(PK)││(PK)│
└────┘└────┘│└────┘└────┘└────┘
             │
             └────────── 叶子节点双向链表 ──→ 用于范围扫描
```

**聚簇索引（Clustered Index）:**
- InnoDB 表必须有且只有一个聚簇索引
- 叶子节点存储完整行数据（Record + 行数据）
- 如果没有显式定义主键，InnoDB 会使用隐藏的 `row_id` 作为聚簇索引
- 如果有唯一索引，使用该唯一索引作为聚簇索引

**二级索引（Secondary Index）:**
- 叶子节点存储：索引列值 + 主键值
- 查询时先查二级索引找到主键，再回表查聚簇索引（覆盖索引可避免回表）

### 3.3 覆盖索引（Covering Index）

```
-- 覆盖索引: 查询的列都在索引中，无需回表
SELECT id, name FROM user WHERE age = 25;
  -- 如果 (age, name) 有联合索引，则不需要回表

-- 回表过程:
-- 1. 在二级索引 B+Tree 中找到 (age=25, id=123)
-- 2. 用 id=123 去聚簇索引 B+Tree 中查找完整行
-- 3. 返回 name

-- 优化: 使用覆盖索引避免回表
ALTER TABLE user ADD INDEX idx_age_name (age, name);
-- 现在查询可以直接从二级索引返回，无需回表
```

### 3.4 索引下推（Index Condition Pushdown, ICP）

```
-- MySQL 5.6+ 优化: 在存储引擎层过滤，减少回表次数

-- 无 ICP:
-- 1. 二级索引遍历所有 age >= 20 的记录
-- 2. 每条都回表查聚簇索引
-- 3. 在 Server 层过滤 name LIKE '%张%'
-- N 次回表

-- 有 ICP:
-- 1. 二级索引遍历 age >= 20
-- 2. 在存储引擎层直接用 name LIKE '%张%' 过滤
-- 3. 只回表查满足条件的记录
-- M 次回表 (M << N)
```

### 3.5 最左前缀原则

```sql
-- 联合索引 (a, b, c) 的 B+Tree 结构:

-- 索引中的记录按 (a, b, c) 排序
a=1, b=1, c=1
a=1, b=1, c=2
a=1, b=2, c=1
a=2, b=1, c=1
a=2, b=2, c=1

-- 能走索引:
WHERE a = 1           ✓ (最左前缀 a)
WHERE a = 1 AND b = 2 ✓ (最左前缀 a, b)
WHERE a = 1 AND b = 2 AND c = 3 ✓ (全部)
WHERE b = 2           ✗ (没有 a，跳过了最左)

-- 范围查询后的列不走索引:
WHERE a = 1 AND b > 2 AND c = 3
  -- a 和 b 能走索引，c 不能（b 是范围查询）
```

---

## 4. MVCC（多版本并发控制）

### 4.1 什么是 MVCC？

```
MVCC (Multi-Version Concurrency Control):
  非锁定并发控制机制，通过数据的多版本实现读写不阻塞

解决的问题:
  1. 读不加锁，读写不冲突 → 提高并发
  2. 在可重复读隔离级别下，解决脏读、不可重复读
  3. 在读已提交和可重复读下，解决部分幻读

实现方式:
  1. 隐藏列: DB_TRX_ID, DB_ROLL_PTR, DB_ROW_ID
  2. Undo Log: 版本链（Version Chain）
  3. Read View: 可见性判断
```

### 4.2 InnoDB 隐藏列

```
每行记录额外包含 3 个隐藏列:

DB_TRX_ID (6B):
  最近修改该行的事务 ID
  插入时填入事务 ID
  更新时填入新事务 ID

DB_ROLL_PTR (7B):
  回滚指针，指向 Undo Log 中的前一个版本
  形成版本链

DB_ROW_ID (6B):
  隐含行 ID（如果没有主键或唯一索引时自动生成）
  单调递增
```

### 4.3 Undo Log 版本链

```
记录修改过程:

原始记录:  (id=1, name='A', trx_id=10, roll_ptr→V1)
  │
  ▼ 事务 20 更新 name='B'
新版本:    (id=1, name='B', trx_id=20, roll_ptr→V1)
  │
  ▼ Undo Log V1: (id=1, name='A', trx_id=10, roll_ptr→0)

版本链: V2 → V1 → V0 (V2 是最新版本)

查询时的版本链遍历:
  Read View 可见性判断
  ┌─────────────────────────────────────┐
  │ 如果当前事务能看到 trx_id=20 的版本 │
  │   → 返回 name='B'                   │
  │ 如果看不到 trx_id=20 的版本         │
  │   → 顺着 roll_ptr 找 V1             │
  │   → 检查 V1 的 trx_id=10 是否可见   │
  │   → 如果可见，返回 name='A'         │
  └─────────────────────────────────────┘
```

### 4.4 Read View（读视图）

```
Read View 是 MVCC 的核心，决定事务能看到哪些版本:

Read View 结构:
  struct ReadView {
    trx_id_t min_trx_id;   // 活跃事务最小 ID
    trx_id_t max_trx_id;   // 下一个将要分配的事务 ID
    trx_id_t* creator_trx_id;  // 创建 Read View 的事务 ID
    m_trx_ids;             // 创建 Read View 时的活跃事务 ID 列表
  }

可见性判断规则:
  ┌──────────────────────────────────────────────────────────────┐
  │ trx_id < min_trx_id       → 可见（事务已提交）               │
  │ trx_id >= max_trx_id      → 不可见（事务未开始）             │
  │ min_trx_id <= trx_id < max_trx_id                        │
  │   如果 trx_id 在 m_trx_ids 中 → 不可见（当前活跃事务）        │
  │   如果 trx_id 不在 m_trx_ids 中 → 可见（已提交）             │
  └──────────────────────────────────────────────────────────────┘
```

### 4.5 隔离级别与 Read View

```
隔离级别:

READ UNCOMMITTED (读未提交):
  不加 Read View，直接读最新数据
  → 脏读、不可重复读、幻读

READ COMMITTED (读已提交) - MySQL 默认:
  每次 SELECT 都创建新的 Read View
  → 每次读取都看到最新提交的数据
  → 不可重复读

REPEATABLE READ (可重复读) - InnoDB 默认:
  第一次 SELECT 创建 Read View，后续 SELECT 复用
  → 整个事务中看到一致的数据快照
  → 解决了不可重复读
  → 通过 Next-Key Lock 解决大部分幻读

SERIALIZABLE (串行化):
  对所有读加 S 锁
  → 完全串行执行
```

### 4.6 RC 和 RR 的区别

```
-- RC (Read Committed): 每次查询都创建新 Read View
BEGIN;
  SELECT * FROM user WHERE id=1;  -- ReadView_A
  -- 事务 A 提交 name='B'
  SELECT * FROM user WHERE id=1;  -- ReadView_B (新读视图)
  -- 能看到 name='B' (不可重复读)

-- RR (Repeatable Read): 第一次查询创建 Read View，后续复用
BEGIN;
  SELECT * FROM user WHERE id=1;  -- ReadView_A (创建)
  -- 事务 A 提交 name='B'
  SELECT * FROM user WHERE id=1;  -- 复用 ReadView_A
  -- 看不到 name='B' (可重复读)
```

### 4.7 当前读 vs 快照读

```
快照读（Snapshot Read）:
  普通的 SELECT 语句
  读取的是数据的历史版本（MVCC）
  不加锁

当前读（Current Read）:
  会读取最新的数据版本
  加锁（共享锁/排他锁）
  
  当前读语句:
  SELECT ... LOCK IN SHARE MODE   -- 共享锁（S锁）
  SELECT ... FOR UPDATE            -- 排他锁（X锁）
  INSERT                             -- 排他锁
  UPDATE                             -- 排他锁
  DELETE                             -- 排他锁
  LOCK TABLES                        -- 表锁
```

---

## 5. 锁机制

### 5.1 锁的分类

```
按粒度:
  ├── 全局锁: FLUSH TABLES WITH READ LOCK
  ├── 表级锁:
  │   ├── 表锁（Table Lock）
  │   └── 元数据锁（MDL, Metadata Lock）
  └── 行级锁（Row Lock） ← InnoDB 主要使用
      ├── 记录锁（Record Lock）: 锁住一条记录
      ├── 间隙锁（Gap Lock）: 锁住一个范围（不包含记录）
      └── 临键锁（Next-Key Lock）: Record Lock + Gap Lock

按性质:
  ├── 共享锁（S锁/Read Lock）: 允许多个事务读取
  └── 排他锁（X锁/Write Lock）: 只允许一个事务写入
```

### 5.2 Next-Key Lock

```
Next-Key Lock = Record Lock + Gap Lock

示例: 索引字段 age 上有唯一索引

索引值: 10, 20, 30, 40, 50

-- UPDATE user SET name='X' WHERE age = 20;
  → 加 Record Lock 在 (20) 这条记录上
  
-- UPDATE user SET name='X' WHERE age = 15;
  → 加 Gap Lock 在 (10, 20) 这个间隙上
  → 防止其他事务在 (10, 20) 之间插入 15
  
-- UPDATE user SET name='X' WHERE age = 25;
  → 加 Gap Lock 在 (20, 30) 这个间隙上

-- UPDATE user SET name='X' WHERE age = 55;
  → 加 Gap Lock 在 (50, +∞) 这个间隙上（上界是正无穷）

RR 级别下，InnoDB 默认使用 Next-Key Lock 防止幻读
```

### 5.3 死锁与解决

```
死锁场景:
  事务 A: LOCK IN SHARE MODE WHERE id=1; → LOCK IN SHARE MODE WHERE id=2;
  事务 B: LOCK IN SHARE MODE WHERE id=2; → LOCK IN SHARE MODE WHERE id=1;

  A 等 B 释放 id=2 的锁，B 等 A 释放 id=1 的锁 → 死锁

InnoDB 死锁检测:
  1. 等待图（Wait-for Graph）: 事务 A 等 B，B 等 A → 环 → 死锁
  2. 选择一个事务回滚（通常选择回滚代价小的，即修改行数少的）
  3. 返回死锁错误: `Deadlock found when trying to get lock`

避免死锁:
  1. 按固定顺序访问资源（如 always 先锁 id=1 再锁 id=2）
  2. 一次性申请所有锁
  3. 使用 NOWAIT 或 SET innodb_lock_wait_timeout
  4. 缩短事务范围，减少持锁时间
```

### 5.4 锁等待监控

```sql
-- 查看当前锁等待
SELECT * FROM information_schema.innodb_locks;
SELECT * FROM information_schema.innodb_lock_waits;

-- MySQL 8.0+ 更直观的监控
SELECT * FROM performance_schema.data_locks;
SELECT * FROM performance_schema.data_lock_waits;

-- 监控锁等待
SHOW ENGINE INNODB STATUS\G
-- 关注 "LATEST DETECTED DEADLOCK" 部分
```

---

## 6. 事务与 XA

### 6.1 事务 ACID

```
Atomicity (原子性):
  通过 Undo Log 实现
  回滚段记录修改前的值，事务失败时回滚

Consistency (一致性):
  所有其他特性的最终目标
  
Isolation (隔离性):
  通过 MVCC + 锁实现
  
Durability (持久性):
  通过 Redo Log 实现
  WAL (Write-Ahead Logging): 先写日志，再写数据
```

### 6.2 Redo Log 机制

```
Redo Log (重做日志):
  物理日志，记录"在某个数据页上做了什么修改"
  
  循环写入: redo_log 是固定大小的（innodb_log_files_in_group * innodb_log_file_size）
  写满后从头开始覆盖（LSN 回绕）
  
  写入流程:
  1. 修改 Buffer Pool 中的数据页（标记为 dirty page）
  2. 同时生成 Redo Log 写入 redo log buffer
  3. Redo Log Buffer 刷新到磁盘（取决于 flush 策略）

刷盘策略（innodb_flush_log_at_trx_commit）:
  0: 每秒刷一次 Redo Log → 高性能，崩溃可能丢 1 秒数据
  1: 每次事务提交刷一次 → 最安全，性能开销最大（默认）
  2: 每次事务提交写入 OS Buffer，每秒刷一次 → 折中
```

### 6.3 XA 分布式事务

```
XA 两阶段提交（2PC）:

Phase 1: Prepare（准备阶段）
  ├── 各参与者执行事务，写入 undo + redo
  ├── 各参与者 PREPARE 事务
  ├── 各参与者写入 XA 日志（prepare 状态）
  └── 各参与者返回 PREPARED 给 Coordinator

Phase 2: Commit（提交阶段）
  ├── 如果所有参与者 PREPARED:
  │   ├── Coordinator 发送 COMMIT
  │   └── 各参与者提交事务，清理 XA 日志
  └── 如果任一参与者失败:
      ├── Coordinator 发送 ROLLBACK
      └── 各参与者回滚事务

性能问题:
  - 两阶段提交导致锁持有时间长
  - Coordinator 单点故障风险
  - 阻塞型：prepare 后锁不释放，直到 commit/rollback

MySQL XA 示例:
  XA START 'tx1';
  INSERT INTO t VALUES (1);
  XA PREPARE 'tx1';
  XA COMMIT 'tx1';

MySQL 8.0: 支持 Group Commit + Optimistic XA 优化
```

### 6.4 binlog 与 Redo Log 关系

```
MySQL 两阶段提交（协调 binlog 和 redo log）:

1. 执行引擎生成 redo log（写入 redo log buffer）
2. 存储引擎提交事务，redo log flush（fsync）
3. 存储引擎返回执行引擎
4. 执行引擎生成 binlog（写入 binlog buffer）
5. 事务提交，binlog flush（fsync） ← 关键！
6. 如果 binlog flush 成功但 redo 未 flush → 通过回滚 undo log 补偿
7. 如果 redo flush 成功但 binlog 未 flush → crash recovery 时 binlog 没有该事务，主从复制不一致

 innodb_flush_log_at_trx_commit=1 + sync_binlog=1 保证最强一致性
  innodb_flush_log_at_trx_commit=1: redo log 每次提交刷盘
  sync_binlog=1: binlog 每次提交刷盘
```

---

## 7. 性能优化

### 7.1 慢查询优化

```sql
-- 开启慢查询日志
SET global slow_query_log = 'ON';
SET global long_query_time = 1;  -- 超过 1 秒的查询记录

-- 分析慢查询
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

-- EXPLAIN 分析
EXPLAIN SELECT * FROM user WHERE age = 25 AND city = '北京';

-- 关注: type, key, rows, Extra
-- type 从优到劣: system > const > eq_ref > ref > range > index > ALL
-- Extra 关键: Using filesort（需要排序）, Using temporary（需要临时表）, Using index（覆盖索引）
```

### 7.2 索引优化原则

```
1. 最左前缀: 联合索引按最左前缀匹配
2. 选择性: 高选择性字段放前面（如 status 区分度低，放后面）
3. 覆盖索引: 尽量用覆盖索引避免回表
4. 索引下推: MySQL 5.6+ 支持 ICP
5. 前缀索引: 对长字符串使用前缀索引
6. 索引下推: SELECT * 避免回表，只 SELECT 需要的列

避免:
  - WHERE 中对索引列使用函数 → 索引失效
  - LIKE '%xxx' 前缀模糊查询 → 索引失效
  - 隐式类型转换 → 索引失效
  - OR 连接条件，一边有索引一边没有 → 索引失效
```

### 7.3 参数调优

```
关键参数:
  innodb_buffer_pool_size = 物理内存的 60-70%
  innodb_log_file_size = 256M-1G（越大写入越快，但崩溃恢复越慢）
  innodb_flush_log_at_trx_commit = 1（强一致性）/ 0（高性能）
  innodb_flush_method = O_DIRECT（避免双重缓冲）
  innodb_io_capacity = 2000（SSD 调高，HDD 保持默认）
  innodb_read_io_threads = 8
  innodb_write_io_threads = 8
  innodb_thread_concurrency = 0（不限制，根据 CPU 调整）

连接池:
  max_connections = 500-1000
  wait_timeout = 600
  interactive_timeout = 600
```

### 7.4 分库分表

```
垂直分表:
  - 大字段拆到扩展表（TEXT/BLOB）
  - 热点字段和不热点字段分离

水平分表:
  - 按用户 ID 取模: shard_id = user_id % N
  - 按时间范围: 按月/年分表
  
中间件:
  - ShardingSphere
  - Vitess (YouTube)
  - TiDB (NewSQL，透明分片)

一致性挑战:
  - 跨分片 JOIN
  - 跨分片分页
  - 分布式主键（雪花算法 UUID）
  - 分布式事务（Saga / TCC / AT）
```

---

## 8. 排障实战

### 8.1 连接数爆满

```sql
-- 查看连接数
SHOW STATUS LIKE 'Threads%';
-- Threads_connected: 当前连接数
-- Threads_created: 总共创建连接数
-- Threads_running: 当前活跃连接数

-- 排查慢查询导致连接堆积
SHOW PROCESSLIST;
-- 或
SELECT * FROM information_schema.processlist WHERE COMMAND != 'Sleep';

-- 解决:
-- 1. 优化慢查询
-- 2. 增加连接池大小
-- 3. 缩短事务时间
-- 4. 检查连接泄漏（应用未关闭连接）
```

### 8.2 CPU 飙高

```sql
-- 查看 CPU 使用最高的查询
SELECT * FROM sys.session GROUP BY last_seen ORDER BY last_seen DESC LIMIT 10;

-- 查看 IO 等待
SELECT * FROM sys.x_io_by_thread_by_latency;

-- 常见原因:
-- 1. 全表扫描（缺索引）
-- 2. 大事务（undo 过多）
-- 3. 排序/临时表（Using filesort/Using temporary）
-- 4. 锁等待（InnoDB row lock wait）
```

### 8.3 死锁排查

```sql
-- 查看最近死锁
SHOW ENGINE INNODB STATUS\G
-- 查看 LATEST DETECTED DEADLOCK 部分

-- 优化方向:
-- 1. 按固定顺序访问资源
-- 2. 减少事务范围
-- 3. 使用 NOWAIT
-- 4. 降低隔离级别到 RC（如果业务允许）
```

---

*本文档基于 MySQL 8.0 整理，涵盖了 InnoDB 内核核心机制*
