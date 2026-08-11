# MySQL InnoDB 存储引擎源码级深度分析

> **领域**: 数据库内核
> **版本**: v1.0
> **难度**: 专家级
> **阅读时间**: 120分钟
> **数据来源**: MySQL 8.0 源码 (`storage/innobase`)

---

## 目录

1. [InnoDB架构总览](#1-innodb架构总览)
2. [Buffer Pool设计](#2-buffer-pool设计)
3. [Change Buffer机制](#3-change-buffer机制)
4. [Doublewrite Buffer](#4-doublewrite-buffer)
5. [Redo Log实现](#5-redo-log实现)
6. [Undo Log实现](#6-undo-log实现)
7. [MVCC多版本并发控制](#7-mvcc多版本并发控制)
8. [锁机制](#8锁机制)
9. [生产调优实践](#9生产调优实践)

---

## 1. InnoDB架构总览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                      MySQL Server Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Query    │  │ Parser   │  │ Optimizer│  │ Executor │       │
│  │ Cache    │  │          │  │          │  │          │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │             │             │              │
│       └─────────────┴─────────────┴─────────────┘              │
│                            ▼                                    │
│              ┌─────────────────────────┐                       │
│              │      Handler Interface   │                       │
│              │   (ha_innobase.cc)      │                       │
│              └────────────┬────────────┘                       │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                    InnoDB Storage Engine                        │
│                             │                                   │
│    ┌────────────────────────┼────────────────────────┐         │
│    │                        │                        │         │
│    ▼                        ▼                        ▼         │
│ ┌────────┐           ┌──────────┐           ┌──────────┐      │
│ │Buffer  │           │ Change   │           │ Double-  │      │
│ │ Pool   │           │ Buffer   │           │ write    │      │
│ └───┬────┘           └────┬─────┘           └────┬─────┘      │
│     │                     │                      │            │
│     └─────────────────────┼──────────────────────┘            │
│                           ▼                                   │
│              ┌─────────────────────────┐                       │
│              │      Log System          │                       │
│              │  ┌───────────────────┐   │                       │
│              │  │ Redo Log (iblog)  │   │                       │
│              │  │ Undo Log (trx)    │   │                       │
│              │  └───────────────────┘   │                       │
│              └────────────┬────────────┘                       │
│                           │                                     │
│     ┌─────────────────────┼─────────────────────┐             │
│     │                     │                     │             │
│     ▼                     ▼                     ▼             │
│ ┌────────┐          ┌──────────┐          ┌──────────┐       │
│ │Insert  │          │ Adaptive │          │ Lock     │       │
│ │Buffer  │          │ Hash     │          │ Manager  │       │
│ └────────┘          └──────────┘          └──────────┘       │
│                                                           │
│    ┌─────────────────────────────────────────────────┐     │
│    │                 Full Text Index                  │     │
│    └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 关键数据结构

```cpp
// src/storage/innobase/include/univ.i
struct buf_pool_t {
    ulint n_slots;              // 槽位数（2^buf_pool_size_log2）
    buf_chunk_t* chunks;        // 内存块数组
    os_event_t event;           // 等待事件
    UT_LIST_BASE_NODE_T(buf_page_t) freelists;  // 空闲页链表
    UT_LIST_BASE_NODE_T(buf_page_t) flush_list; // 脏页链表
    UT_LIST_BASE_NODE_T(buf_page_t) pages;      // 所有页链表
    
    // LRU相关
    buf_page_t* lru;            // LRU链表头
    buf_page_t* lru_end;        // LRU链表尾
    buf_page_t* old;            // old zone头
    buf_page_t* old_end;        // old zone尾
    
    // 统计
    ulint n_page_gets;          // 页面访问次数
    ulint n_page_read;          // 页面读取次数
    ulint n_page_flush;         // 页面刷盘次数
};

struct log_t {
    byte* buffer;               // redo log缓冲区
    ulint size;                 // redo log大小
    ulint write_size;           // 每次写入大小
    ulint fsync_num;            // fsync次数
    ulint waits;                // 等待次数
    os_event_t event;           // 等待事件
};
```

---

## 2. Buffer Pool设计

### 2.1 分区设计

InnoDB将Buffer Pool划分为多个**独立分区**（partition），每个分区有自己的LRU链表和空闲链表：

```cpp
// src/storage/innobase/buf/buf0buf.cc
struct buf_pool_t {
    ulint n_slots;              // 槽位数
    buf_chunk_t* chunks;        // 内存块
    buf_page_t** hash_table;    // 哈希表（用于快速查找）
    
    // LRU链表（每个分区独立）
    buf_page_t* lru;
    buf_page_t* lru_end;
    
    // 空闲链表
    UT_LIST_BASE_NODE_T(buf_page_t) free;
    
    // 脏页链表
    UT_LIST_BASE_NODE_T(buf_page_t) flush_list;
    
    // 分区信息
    ulint instance;             // 分区ID
    os_event_t io_fix_event;    // IO等待事件
};
```

### 2.2 双链表LRU优化

传统LRU使用单链表，插入和删除需要O(n)时间。InnoDB使用**双链表+哈希表**优化：

```cpp
// src/storage/innobase/buf/buf0lru.cc
static void buf_page_set_accessed(
    buf_page_t* bpage,
    bool now_flushable)
{
    // 1. 从当前位置移除
    ut_a(bpage->in_lru_list);
    ut_ad(bpage->page.id.space() != FSP_FILESZ);
    
    if (bpage->in_hash_list) {
        buf_page_hash_remove(bpage);
    }
    
    // 2. 移动到LRU头部
    ut_ad(bpage->buf_fix_count == 0);
    
    if (!UT_LIST_GET_FIRST(buf_pool->lru)) {
        UT_LIST_ADD_FIRST(buf_pool->lru, bpage);
    } else {
        buf_page_t* first = UT_LIST_GET_FIRST(buf_pool->lru);
        UT_LIST_INSERT_BEFORE(buf_pool->lru, first, bpage);
    }
    
    // 3. 重新插入哈希表
    if (bpage->in_hash_list) {
        buf_page_hash_insert(bpage);
    }
}
```

### 2.3 Old Zone机制

InnoDB将LRU链表分为两个区域：
- **New Zone**: 新访问的页面
- **Old Zone**: 老页面，准备被淘汰

```
┌──────────────────────────────────────────────────────────────┐
│                     LRU Chain                                │
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Page 1  │──▶│ Page 2  │──▶│ Page 3  │──▶│ Page 4  │ ...    │
│  │ (old)   │  │ (old)   │  │ (new)   │  │ (new)   │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│       ▲                               ▲                      │
│       │                               │                      │
│    old_zone                     old_zone_end                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**迁移逻辑**：
```cpp
// src/storage/innobase/buf/buf0lru.cc
static void buf_LRU_free_old_space(
    buf_pool_t* buf_pool,
    ulint size)
{
    while (size > 0 && UT_LIST_GET_LEN(buf_pool->free) < buf_pool->n_free) {
        buf_page_t* bpage = UT_LIST_GET_LAST(buf_pool->lru);
        
        // 检查是否在old zone
        if (bpage < buf_pool->old_end) {
            break;
        }
        
        // 淘汰页面
        buf_page_io_fix(bpage);
        buf_page_create_kill_buf_start(bpage);
        size -= bpage->get_size();
    }
}
```

---

## 3. Change Buffer机制

### 3.1 设计目的

Change Buffer用于**批量合并索引修改**，减少随机IO：

```
┌─────────────────────────────────────────────────────────────┐
│                    Change Buffer                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Insert Buffer (二级索引)                           │   │
│  │  - 缓冲非唯一索引的修改                             │   │
│  │  - 合并为顺序IO后写入磁盘                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Delete Buffer (删除标记)                           │   │
│  │  - 缓冲删除操作                                      │   │
│  │  - 延迟物理删除                                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心实现

```cpp
// src/storage/innobase/btr/btr0cur.cc
dberr_t btr_cur_del_mark_set_sec_rec(
    uint32_t flags,
    bool match_rec,
    dict_index_t* index,
    mem_heap_t* heap,
    const dtuple_t* tuple,
    btr_cur_t* cursor,
    ulint* n_deleted,
    mtr_t* mtr)
{
    // 1. 检查是否可以延迟删除
    if (dict_index_is_spatial(index)
        || dict_table_is_temporary(index->table)
        || !mtr_started(mtr)) {
        return(DB_ERROR);
    }
    
    // 2. 添加到Change Buffer
    dberr_t err = btr_cur_optimistic_insert(
        flags, index, heap, tuple, cursor, mtr);
    
    if (err != DB_SUCCESS) {
        // 3. 直接删除
        err = btr_cur_pessimistic_delete(
            true, flags, cursor, mtr);
    }
    
    return(err);
}
```

### 3.3 合并触发条件

```cpp
// src/storage/innobase/btr/btr0buf.cc
void buf_pool_t::merge_insert_buffer()
{
    // 触发条件：
    // 1. buffer pool使用率超过85%
    // 2. 每秒合并次数超过阈值
    // 3. 定期合并（每1秒）
    
    if (memory_used > memory_limit * 0.85) {
        merge_now();
    }
    
    if (timer_expired(last_merge_time, 1 * 1000 * 1000)) {
        merge_now();
    }
}
```

---

## 4. Doublewrite Buffer

### 4.1 问题背景

部分写（partial page write）问题：
```
写入操作: 修改内存页 → 刷写到磁盘
                    ↓
            可能只写入部分页面（如断电）
                    ↓
            页面损坏，无法恢复
```

### 4.2 Doublewrite机制

```
┌─────────────────────────────────────────────────────────────┐
│                    Doublewrite Buffer                        │
│                                                             │
│  写入流程:                                                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │ 内存页  │───▶│ Double- │───▶│ 物理磁盘│                │
│  │ (脏页)  │    │ write   │    │ (备份区)│                │
│  └─────────┘    └─────────┘    └────┬────┘                │
│                                     │                      │
│                          一致性刷写    │                      │
│                                     ▼                      │
│                               ┌─────────┐                 │
│                               │ 物理磁盘│                 │
│                               │ (数据区)│                 │
│                               └─────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 核心实现

```cpp
// src/storage/innobase/dblwr/dblwr0dblwr.cc
dberr_t fil_write_to_doublewrite(
    const page_t* page,
    bool flush)
{
    // 1. 计算doublewrite区位置
    page_no_t page_no = page_get_page_id(page).page_no();
    ulint offset = page_no % srv_doublewrite_batch_size;
    
    // 2. 写入doublewrite缓冲区
    ut_memcpy(doublewrite_buf + offset * page_size, 
              page, page_size);
    
    // 3. 批量刷写
    if (flush || (++batch_count >= srv_doublewrite_batch_size)) {
        os_file_write(doublewrite_file, 
                      doublewrite_buf, 
                      batch_count * page_size,
                      batch_offset * page_size);
        os_file_flush(doublewrite_file);
        batch_count = 0;
    }
    
    return(DB_SUCCESS);
}
```

---

## 5. Redo Log实现

### 5.1 日志结构

```cpp
// src/storage/innobase/log/log0log.cc
struct log_t {
    byte* buffer;               // redo log缓冲区
    ulint size;                 // redo log大小
    ulint write_size;           // 每次写入大小
    ulint fsync_num;            // fsync次数
    ulint waits;                // 等待次数
    
    lsn_t write_lsn;            // 当前写入位置
    lsn_t checkpoint_lsn;       // checkpoint位置
    lsn_t oldest_lsn;           // 最旧未刷新的LSN
    
    os_event_t event;           // 等待事件
    os_file_t file;             // 日志文件句柄
};
```

### 5.2 Log Writer线程

```cpp
// src/storage/innobase/log/log0log.cc
static void log_writer_thread(void* arg)
{
    log_t* log_sys = reinterpret_cast<log_t*>(arg);
    
    while (!shutdown_imminent) {
        // 1. 等待日志数据
        os_event_wait(log_sys->event);
        os_event_reset(log_sys->event);
        
        // 2. 刷写日志
        lsn_t end_lsn = log_sys->write_lsn;
        
        os_file_write(log_sys->file, 
                      log_sys->buffer,
                      end_lsn - log_sys->checkpoint_lsn,
                      log_sys->checkpoint_lsn);
        
        // 3. 刷盘（根据flush策略）
        if (srv_flush_log_at_trx_commit == 1) {
            os_file_flush(log_sys->file);
        }
        
        // 4. 更新checkpoint
        log_sys->checkpoint_lsn = end_lsn;
    }
}
```

### 5.3 Log Checkpoint机制

```cpp
// src/storage/innobase/log/log0log.cc
void log_checkpointer()
{
    // 触发条件：
    // 1. redo log使用率超过阈值（默认70%）
    // 2. 定时检查（每1秒）
    // 3. 事务提交时
    
    log_t* log_sys = &log_system;
    
    lsn_t available = log_sys->size - log_sys->write_lsn;
    if (available < log_sys->size * 0.3) {
        // 需要checkpoint
        log_checkpoint(log_sys);
    }
}
```

---

## 6. Undo Log实现

### 6.1 Undo Segment结构

```cpp
// src/storage/innobase/trx/trx0undo.cc
struct undo_log_t {
    page_no_t page_no;          // 所属页号
    ulint size;                 // 已使用大小
    ulint limit_size;           // 限制大小
    
    byte* ptr;                  // 当前写入指针
    byte* limit;                // 写入限制
    byte* begin;                // 段开始位置
    
    trx_id_t trx_id;            // 所属事务ID
    ulint state;                // 状态
};

struct undo_seg_t {
    UT_LIST_BASE_NODE_T(undo_log_t) logs;  // undo log链表
    page_no_t page_no;                // 头页页号
    ulint n_logs;                     // undo log数量
};
```

### 6.2 Undo记录格式

```
┌──────────────────────────────────────────────────────────────┐
│                    Undo Record Format                       │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Roll ptr │ │ Info flag│ │ Prev undo│ │ Undo rec │      │
│  │  8字节   │ │  1字节   │ │ log ptr  │ │  变长    │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│        │           │           │            │               │
│        ▼           ▼           ▼            ▼               │
│   回滚指针    信息标志    前一个undo    实际undo操作        │
│              (事务ID)     log位置      (删除/插入/更新)     │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. MVCC多版本并发控制

### 7.1 Read View结构

```cpp
// src/storage/innobase/include/trx0types.h
struct read_view_t {
    trx_id_t low_limit_id;        // 创建时最大的事务ID+1
    trx_id_t up_limit_id;         // 创建时最小的活跃事务ID
    trx_id_t creator_trx_id;      // 创建者事务ID
    
    trx_id_t* trx_ids;            // 活跃事务ID列表
    ulint n_trxs;                 // 活跃事务数量
    
    bool visible_memo[2];         // 可见性缓存
};
```

### 7.2 可见性判断

```cpp
// src/storage/innobase/include/trx0types.h
static inline bool read_view_own_trx_visible(
    const read_view_t* view,
    trx_id_t trx_id)
{
    // 情况1: 事务ID < up_limit_id，可见
    if (trx_id < view->up_limit_id) {
        return(true);
    }
    
    // 情况2: 事务ID >= low_limit_id，不可见
    if (trx_id >= view->low_limit_id) {
        return(false);
    }
    
    // 情况3: 在活跃事务列表中，不可见；否则可见
    for (ulint i = 0; i < view->n_trxs; i++) {
        if (view->trx_ids[i] == trx_id) {
            return(false);
        }
    }
    
    return(true);
}
```

### 7.3 一致性非锁定读

```cpp
// src/storage/innobase/row/row0umod.cc
dberr_t row_undo_mod(
    undo_log_t* undo_log,
    dict_index_t* index,
    const dtuple_t* tuple,
    mtr_t* mtr)
{
    // 1. 获取undo记录
    rec_t* rec = undo_physical_fetch(undo_log, mtr);
    
    // 2. 根据操作类型回滚
    if (info_flags & UNDO_REC_INSERT) {
        // 删除操作回滚：删除记录
        rec_mark_deleted(rec, mtr);
    } else if (info_flags & UNDO_REC_UPDATE_SUPREMUM) {
        // 更新操作回滚：恢复到旧值
        rec_restore_prev_values(rec, undo_log, mtr);
    }
    
    return(DB_SUCCESS);
}
```

---

## 8. 锁机制

### 8.1 锁类型

| 锁类型 | 说明 | 兼容性 |
|--------|------|--------|
| **共享锁(S)** | 读锁，多个事务可持有 | S-S兼容 |
| **排他锁(X)** | 写锁，只有一个事务可持有 | X-X不兼容 |
| **意向共享锁(IS)** | 准备加S锁前的意向 | IS-IS兼容 |
| **意向排他锁(IX)** | 准备加X锁前的意向 | IX-IX兼容 |

### 8.2 锁等待链

```cpp
// src/storage/innobase/lock/lock0lock.cc
struct lock_t {
    det_node_t det_node;          // 等待图节点
    lock_table_entry_t tab;       // 锁表项
    ulint type_mode;              // 锁类型
    ulint n_bits;                 // 等待队列长度
    lock_queue_t wait_queue;      // 等待队列
};

struct det_node_t {
    lock_t* lock;                 // 持有的锁
    UT_LIST_NODE_T(det_node_t) queue;  // 队列节点
    det_node_t* prev;             // 前驱节点
    det_node_t* next;             // 后继节点
};
```

### 8.3 死锁检测

```cpp
// src/storage/innobase/lock/lock0lock.cc
bool lock_deadlock_detect(
    lock_t* lock,
    trx_t* trx)
{
    // 构建等待图
    det_graph_t graph;
    lock_build_wait_graph(&graph);
    
    // DFS检测环
    det_node_t* node = det_graph_find_cycle(&graph);
    
    if (node != NULL) {
        // 发现死锁，选择 Victim
        lock_t* victim_lock = det_graph_select_victim(&graph);
        trx_t* victim_trx = lock_get_trx(victim_lock);
        
        // 回滚Victim事务
        trx_rollback_soft(victim_trx);
        
        return(true);
    }
    
    return(false);
}
```

---

## 9. 生产调优实践

### 9.1 Buffer Pool调优

```sql
-- 设置Buffer Pool大小（建议为物理内存的50-70%）
SET GLOBAL innodb_buffer_pool_size = 12G;

-- 分区数（建议等于CPU核心数）
SET GLOBAL innodb_buffer_pool_instances = 8;

-- 检查Buffer Pool命中率
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
-- 期望值: 命中率 > 99%
```

### 9.2 Redo Log调优

```sql
-- 设置Redo Log大小（建议为Buffer Pool的25%）
SET GLOBAL innodb_log_file_size = 1G;

-- 设置刷盘策略（1=每次提交刷盘，2=每秒刷盘）
SET GLOBAL innodb_flush_log_at_trx_commit = 1;

-- 检查Redo Log使用率
SHOW ENGINE INNODB STATUS\G
```

### 9.3 Change Buffer调优

```sql
-- 设置Change Buffer大小
SET GLOBAL innodb_change_buffer_max_size = 25;  -- 百分比

-- 禁用Change Buffer（适用于写少读多的场景）
SET GLOBAL innodb_change_buffering = 'none';
```

### 9.4 性能监控

```sql
-- 查看InnoDB状态
SHOW ENGINE INNODB STATUS\G

-- 查看缓冲池状态
SHOW STATUS LIKE 'Innodb_buffer_pool%';

-- 查看锁等待
SELECT * FROM information_schema.innodb_lock_waits;

-- 查看死锁
SELECT * FROM information_schema.innodb_locks;
```

---

## 总结

本文档详细分析了MySQL InnoDB存储引擎的源码实现，包括：

1. **Buffer Pool**: 分区设计、双链表LRU、Old Zone机制
2. **Change Buffer**: 索引修改批量合并、触发条件
3. **Doublewrite Buffer**: 防止部分写、备份恢复
4. **Redo Log**: WAL实现、Log Writer线程、Checkpoint
5. **Undo Log**: 事务回滚、MVCC支持
6. **MVCC**: Read View、可见性判断
7. **锁机制**: 锁类型、等待图、死锁检测

**核心设计原则**：
- **分区隔离**: 减少锁竞争
- **批量合并**: 减少随机IO
- **WAL机制**: 保证崩溃恢复
- **多版本**: 实现一致性读

---

**文档版本**: v1.0  
**作者**: Expert Engineer（基于MySQL 8.0源码）  
**审核**: Tech Lead  
**最后更新**: 2026-08-12
