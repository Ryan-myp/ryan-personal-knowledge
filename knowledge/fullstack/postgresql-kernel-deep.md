# PostgreSQL 内核深度解析

> 深入 PostgreSQL 核心：MVCC实现、WAL日志、查询优化器、扩展机制。
> 源码级分析，包含与MySQL对比。
> 适用对象：DBA、数据库工程师、后端架构师

---

## 1. MVCC 实现原理

### 1.1 核心数据结构

```c
// heapamd.h

typedef struct HeapTupleData {
   ItemIdData t_hoff;      /* 堆元组信息 */
   ItemPointerData t_self; /* 元组RID */
   /* t_ctid 指向本元组的最新副本或下一个版本 */
   ItemPointerData t_ctid;
    /* 以下字段只存在于数据页中的元组 */
   uint32 t_infomask2;     /* 位图信息 */
    uint32 t_infomask;     /* 位图信息 */
    uint24 t_hoff;         /* 变长属性起始位置 */
    uint16 t_bits[1];      /* 位图用于null值 */
    /* 接下来是可选的aligned数据 */
    /* oid --- 只在有oid属性的表中有 */
    /* 接下来是属性值 */
} HeapTupleData;

/* 事务可见性判断 */
#define HeapTupleHeaderGetRawConfidence(tup) \
    ((tup)->t_infomask & HEAP_TUPLE_HAS_SNAPSHOT)
```

### 1.2 版本链结构

```
┌────────────────────────────────────────────────────────────────┐
│                     MVCC 版本链                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  行数据: ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│          │ Version1 │ │Version2  │ │Version3  │              │
│          │ (deleted)│ │ (update) │ │ (current)│              │
│          └────┬─────┘ └────┬─────┘ └────┬─────┘              │
│               │            │            │                      │
│               └────────────┴────────────┘                      │
│                            │                                   │
│               ┌────────────▼────────────┐                     │
│               │    xmin = TID_xmin     │                     │
│               │    xmax = TID_xmax     │                     │
│               └────────────────────────┘                     │
│                                                                │
│  事务ID范围: [1000, 2000]                                      │
│  可见性判断: xmin ≤ cid ≤ xmax                                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 1.3 可见性判断算法

```c
// heapam.c

bool HeapTupleSatisfiesVisibility(HeapTuple heapTuple, Snapshot snapshot, 
                                   Buffer buffer) {
    HeapTupleHeader tuple = heapTuple->t_data;
    
    /* 检查xmin */
    if (TransactionIdPrecedes(tuple->t_xmin, snapshot->xmin)) {
        return true;  /* 事务已提交 */
    }
    if (TransactionIdFollows(tuple->t_xmin, snapshot->xmax)) {
        return false;  /* 事务尚未开始 */
    }
    
    /* 检查xmax */
    if (HeapTupleHeaderIsOnlyComplete(tuple)) {
        return true;
    }
    
    /* 检查tuple状态 */
    if (HeapTupleUpdated(tuple)) {
        return false;  /* 已被更新 */
    }
    
    return false;
}
```

---

## 2. WAL 日志机制

### 2.1 WAL 写入流程

```
┌─────────────────────────────────────────────────────────────┐
│                     WAL 写入流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 修改 Buffer Pool                                       │
│     ┌─────────┐                                             │
│     │ Buffer  │ ← 脏页标记                                  │
│     └─────────┘                                             │
│            │                                                │
│            ▼                                                │
│  2. 写入 WAL 日志                                          │
│     ┌─────────┐                                             │
│     │ WAL Log │ ←  redo/undo 信息                          │
│     └─────────┘                                             │
│            │                                                │
│            ▼                                                │
│  3. fsync 持久化                                            │
│     ┌─────────┐                                             │
│     │ 磁盘    │ ← commit                                    │
│     └─────────┘                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 WAL 配置优化

```sql
-- postgresql.conf

# WAL 基本配置
wal_level = replica              # minimal/replica/logical
max_wal_size = 1GB               # 最大WAL大小
min_wal_size = 80MB              # 最小WAL大小

# 刷盘策略
synchronous_commit = on          # on/off/local
wal_sync_method = fdatasync      # fsync/fdatasync/open_datasync

# 检查点配置
checkpoint_timeout = 10min       # 检查点间隔
checkpoint_completion_target = 0.9  # 检查点完成目标
max_connections = 200            # 最大连接数
```

---

## 3. 查询优化器

### 3.1 查询处理流程

```
                    SQL Query
                        │
                        ▼
              ┌─────────────────┐
              │   Parser        │  语法分析 → 语法树
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Analyzer      │  语义分析 → 分析树
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Planner       │  查询优化 → 执行计划
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Executor      │  执行计划 → 结果
              └─────────────────┘
```

### 3.2 成本模型

```c
// planner.c

typedef struct Path {
    Patentype pathtype;      /* 节点类型 */
    List *param_info;        /* 外部参数 */
    double rows;             /* 预估行数 */
    long startup_cost;       /* 启动成本 */
    long total_cost;         /* 总成本 */
    List *pathkeys;          /* 排序键 */
} Path;

/* 选择最优路径 */
Path *choose_best_path(PlannerInfo *root) {
    List *paths = generate_paths(root);
    Path *best_path = NULL;
    long min_cost = LONG_MAX;
    
    foreach(path, paths) {
        long cost = path->total_cost;
        if (cost < min_cost) {
            min_cost = cost;
            best_path = path;
        }
    }
    
    return best_path;
}
```

---

## 4. 扩展机制

### 4.1 自定义数据类型

```sql
-- 创建复合类型
CREATE TYPE address AS (
    street text,
    city text,
    zip_code text
);

-- 创建表使用复合类型
CREATE TABLE contacts (
    id serial PRIMARY KEY,
    name text,
    address address
);

-- 查询复合类型字段
SELECT (address).city FROM contacts;
```

### 4.2 自定义索引方法

```c
// 自定义索引方法示例
#include "postgres.h"
#include "access/amapi.h"

typedef struct MyIndexAmRoutine {
    IndexAmRoutine amroutine;
} MyIndexAmRoutine;

Datum myindexambuild(PG_FUNCTION_ARGS);
Datum myindexaminsert(PG_FUNCTION_ARGS);

PG_FUNCTION_INFO_V1(myindexambuild);
PG_FUNCTION_INFO_V1(myindexaminsert);

typedef struct MyIndexAmRoutine {
    IndAMBuildFunction build;
    IndAMInsertFunction insert;
} MyIndexAmRoutine;
```

---

## 5. 性能调优

### 5.1 查询优化

```sql
-- 使用 EXPLAIN 分析查询
EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT * FROM orders 
WHERE user_id = 12345 
ORDER BY created_at DESC 
LIMIT 10;

-- 优化建议
-- 1. 添加索引
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at DESC);

-- 2. 使用覆盖索引
CREATE INDEX idx_orders_cover ON orders(user_id, created_at, id, amount);
```

### 5.2 配置优化

```sql
-- 内存配置
shared_buffers = 4GB              -- 共享缓冲区
effective_cache_size = 12GB       -- 有效缓存
work_mem = 64MB                   -- 工作内存
maintenance_work_mem = 512MB      -- 维护内存

-- 查询优化
random_page_cost = 1.1           -- 随机页成本
effective_io_concurrency = 200   -- IO并发数

-- WAL配置
wal_buffers = 64MB               -- WAL缓冲区
```

---

## 6. 与 MySQL 对比

| 特性 | PostgreSQL | MySQL |
|------|------------|-------|
| MVCC | 版本链 | Read View |
| 索引 | B-tree/Hash/GiST/GIN | B-tree/Hash/Fulltext |
| 扩展 | 丰富（类型/索引/函数）| 有限 |
| SQL标准 | 完整支持 | 部分支持 |
| 并发控制 | MVCC + Lock | MVCC + Lock |
| 适用场景 | 复杂查询/OLAP | 简单查询/OLTP |

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 | 关键配置 |
|------|----------|----------|
| MVCC | 版本链 | visibility_map |
| WAL | 预写日志 | wal_level |
| 优化器 | 成本模型 | statistics |
| 扩展 | 插件机制 | ext |

### 7.2 调优 Checklist

- [ ] 设置合适的 shared_buffers
- [ ] 配置 work_mem
- [ ] 调整 WAL 设置
- [ ] 定期 VACUUM
- [ ] 分析慢查询
- [ ] 监控连接数

---

*最后更新：2026-08-11*
*作者：Ryan*
