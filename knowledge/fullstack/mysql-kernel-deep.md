# MySQL InnoDB 内核源码级深度解析

> 深入 MySQL InnoDB 存储引擎核心：事务实现、MVCC、索引结构、锁机制。
> 源码级分析，包含关键数据结构、算法实现、性能调优。
> 适用对象：DBA、后端工程师、数据库内核研究者

---

## 1. InnoDB 架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────────────┐
│                      InnoDB 存储引擎架构                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Buffer Pool │    │  Change      │    │  Redo Log    │          │
│  │  (内存缓冲)   │    │  Buffer      │    │  (重做日志)   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                    │                    │                 │
│         ▼                    ▼                    ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据页管理                                │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │   │
│  │  │ Data    │  │ Index   │  │ Undo    │  │ Foreign │       │   │
│  │  │ Page    │  │ Page    │  │ Page    │  │ Key     │       │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Double      │    │  Adaptive    │    │  Strict     │          │
│  │  Write       │    │  Hash        │    │  Checksum   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据结构

```c
// storage/innobase/include/ buf0buf.h

typedef struct buf_pool_chunk_t buf_pool_chunk_t;
struct buf_pool_chunk_t {
    byte*           start;              /* start of the chunk */
    ulint           n_chunks;           /* number of chunks in this segment */
    oblock_id_t     id;                 /* unique identifier for this chunk */
};

typedef struct buf_pool_t buf_pool_t;
struct buf_pool_t {
    os_event_t      not_full_event;     /* event for when the pool is not full */
    
    ulint           size;               /* number of pages in the pool */
    ulint           n_chunks;           /* number of chunks */
    ulint           n_pages;            /* number of pages in the pool */
    
    ulint*          hash_table;         /* hash table for page lookup */
    ulint           hash_size;          /* hash table size */
    
    buf_chunk_t*    chunks;             /* array of chunks */
    ulint           chunk_size;         /* size of each chunk in pages */
    
    byte**          frame;              /* array of pointers to frames */
    ulint           frame_offset;       /* offset for frame allocation */
    
    ulint           limit_mem_percent;  /* memory limit percentage */
    ulint           max_pages_evicting; /* max pages to evict */
};

// 页头结构
struct page_header_t {
    page_zip_desc_t zip;               /* compressed page zip */
    ut_list_node_t  list;              /* list node */
    ulint           n_used;            /* number of used record slots */
    ulint           n_free;            /* number of free record slots */
    ulint           n_dir_slots;       /* number of directory slots */
    ulint           heap_top;          /* heap top offset */
    ulint           n_fields;          /* number of fields in infimum/supremum */
    ulint           n_records;         /* number of records */
    page_type_t     type;              /* page type */
    fil_addr_t      addr;              /* file address */
    ulint           n_heap;            /* heap number */
    ulint           heap_no;           /* heap number in the page */
    ulint           n_pointers;        /* number of pointers */
    ulint           n_extra;           /* number of extra bytes */
    ulint           n_owned;           /* number of owned records */
    ulint           n_compressed;      /* compressed page size */
};
```

---

## 2. 事务实现

### 2.1 MVCC 多版本并发控制

```c
// storage/innobase/include/univ.i

typedef struct trx_sys_t trx_sys_t;
struct trx_sys_t {
    ulint               size;
    ulint               n_used;
    trx_t**             array;
    ut_ad_list_node_t   list;
};

typedef struct trx_t trx_t;
struct trx_t {
    ulint               id;
    ut_LIST_node_t      list;
    ulint               state;
    enum trx_role       role;
    
    /* Read view */
    trx_read_view_t*    read_view;
    
    /* Transaction IDs */
    ulint               consistent_view_trx_id;
    ulint               consistent_view_lowest_trx_id;
    ulint               consistent_view_next_trx_id;
    
    /* Rollback segment */
    roll_seg_t*         roll_ptr;
    
    /* Locks */
    UT_LIST_BASE_NODE_T(lock_t) locks;
    
    /* Thd */
    ha_thd*             thd;
};
```

### 2.2 Read View 实现

```c
// storage/innobase/include/trx0types.h

typedef struct trx_read_view_t trx_read_view_t;
struct trx_read_view_t {
    ulint               n_ids;
    ulint*              low_limit_id;
    ulint*              up_limit_id;
    ulint*              creator_trx_id;
    ut_list_node_t      view_list;
    bool                empty;
    bool                low_limit_no;
    bool                up_limit_no;
    ulint               up_limit_trx_id;
    ulint               low_limit_trx_id;
};

// 创建 Read View
static inline void trx_read_view_create(trx_read_view_t* view,
                                        trx_id_t up_limit)
{
    ut_ad(view->n_ids == 0);
    view->creator_trx_id = up_limit;
    view->low_limit_id = &up_limit;
    view->up_limit_id = &up_limit;
    view->empty = false;
    view->low_limit_no = false;
    view->up_limit_no = true;
}

// 可见性判断
bool row_clust_rec_seen_before(const rec_t* rec, const dict_index_t* index,
                               const mtr_t* mtr, const trx_read_view_t* view)
{
    if (!view || ! trx_clone_visible(view, rec_get_trx_id(rec, index))) {
        return true;
    }
    return false;
}

bool trx_clone_visible(const trx_read_view_t* view,
                       trx_id_t trx_id)
{
    if (trx_id < view->up_limit_id
        && trx_id >= view->low_limit_id) {
        return true;
    }
    
    for (ulint i = 0; i < view->n_ids; i++) {
        if (view->ids[i] == trx_id) {
            return false;
        }
    }
    
    return true;
}
```

### 2.3 Undo Log 实现

```c
// storage/innobase/include/que0que.h

typedef struct rollback_seg rollback_seg_t;
struct rollback_seg {
    fil_addr_t  page_addr;
    ulint       id;
    bool        empty;
    bool        active;
};

typedef struct undo_log undo_log_t;
struct undo_log {
    fil_addr_t  page_addr;
    ulint       id;
    bool        open;
    ulint       n_ops;
    ut_list_node_t list;
};

// Undo Log 操作
static inline void undo_log_add_row_op(undo_log_t* log,
                                       const byte* ptr, ulint len)
{
    log->n_ops++;
    // 添加到 undo log 记录
    memcpy(log->ptr + log->ptr_len, ptr, len);
    log->ptr_len += len;
}

// 回滚操作
static inline void undo_log_apply(undo_log_t* log, dict_table_t* table)
{
    page_t* page = log_get_page(log->page_addr);
    rec_t* rec = page_get_first(page);
    
    while (!rec_is_infimum(rec)) {
        if (rec_get_deleted_bit(rec)) {
            // 删除记录
            row_del_mark_sec_ind(table, rec);
        } else {
            // 插入记录
            row_ins_sec_index_entry(table->first, rec, false);
        }
        rec = rec_get_next(rec, page_get_n_recs(page));
    }
}
```

---

## 3. 索引结构

### 3.1 B+ 树实现

```c
// storage/innobase/include/btr0btr.h

typedef struct btr_cur_t btr_cur_t;
struct btr_cur_t {
    mtr_t*    mtr;
    page_t*   page;
    rec_t*    rec;
    ulint     level;
    ulint     index_id;
    bool      mode;
};

typedef struct btr_root_t btr_root_t;
struct btr_root_t {
    fil_addr_t addr;
    ulint      level;
    ulint      n_leaf_pages;
    ulint      n_deleted;
    ulint      n_rows;
    ulint      format;
    page_id_t  page_id;
    page_zip_des_t zip;
};

// B+ 树搜索
static inline dberr_t btr_search_on_user_rec(const dtuple_t* tuple,
                                             lock_t lock_mode,
                                             btr_cur_t* cursor,
                                             mtr_t* mtr)
{
    dict_index_t* index = cursor->index;
    page_t* page = btr_block_get(index->table->space,
                                 index->root, PAGE_ROOT,
                                 MTR_MEMO_PAGE_X_FIX, mtr);
    
    rec_t* rec = page_get_infimum_rec(page);
    ulint level = page_get_level(page);
    
    while (level > 0) {
        ulint child_page_no = btr_page_get_left(page, rec, mtr);
        page = btr_block_get(index->table->space, child_page_no,
                            PAGELeaf, MTR_MEMO_PAGE_X_FIX, mtr);
        rec = page_get_infimum_rec(page);
        level--;
    }
    
    // 在叶节点搜索
    while (!rec_is_supremum(rec)) {
        int cmp = dtuple_cmp_with_rec(tuple, rec, index);
        if (cmp <= 0) {
            break;
        }
        rec = rec_get_next(rec, page_get_n_recs(page));
    }
    
    cursor->rec = rec;
    cursor->page = page;
    
    return DB_SUCCESS;
}

// B+ 树插入
static inline dberr_t btr_cur_optimistic_insert(lock_t lock_mode,
                                               const dtuple_t* tuple,
                                               que_thr_t* thread,
                                               btr_cur_t* cursor,
                                               mtr_t* mtr)
{
    page_t* page = cursor->page;
    rec_t* rec = cursor->rec;
    
    // 检查页是否已满
    if (page_get_free_space(page) < dtuple_calc_len(tuple)) {
        // 页分裂
        return btr_page_split_and_insert(lock_mode, tuple, cursor, mtr);
    }
    
    // 插入记录
    btr_cur_insert_to_page(cursor, tuple, mtr);
    
    return DB_SUCCESS;
}
```

### 3.2 聚簇索引与二级索引

```c
// storage/innobase/include/fil0fil.h

// 聚簇索引页结构
typedef struct dict_index_t dict_index_t;
struct dict_index_t {
    dict_table_t* table;
    char* name;
    ulint n_fields;
    ulint n_cols;
    ulint id;
    page_no_t root;
    ulint n_patches;
    ulint n_cols;
    ulint type;  // DICT_CLUSTERED or DICT_FALLBACK
};

// 二级索引页结构
typedef struct dict_col_t dict_col_t;
struct dict_col_t {
    dict_index_t* index;
    ulint pos;
    dtuple_t* field;
};

// 索引操作
static inline rec_t* idx_search(const dtuple_t* tuple,
                               btr_cur_t* cursor,
                               mtr_t* mtr)
{
    dict_index_t* index = cursor->index;
    
    // 如果是二级索引，先找到主键
    if (index->type != DICT_CLUSTERED) {
        dtuple_t* pk_tuple = dtuple_convert_if_needed(index, tuple);
        return btr_search_on_user_rec(pk_tuple, lock_mode, cursor, mtr);
    }
    
    // 聚簇索引直接搜索
    return btr_search_on_user_rec(tuple, lock_mode, cursor, mtr);
}
```

---

## 4. 锁机制

### 4.1 锁数据结构

```c
// storage/innobase/include/lock0lock.h

typedef struct lock lock_t;
struct lock {
    UT_LIST_NODE_T(lock) list;
    
    ut_ad_list_node_t gen_list;
    ut_ad_list_node_t heap_no_list;
    
    hash_table_t* hash_table;
    
    ulint table_id;
    ulint index_id;
    ulint mode_level;
    
    rec_t* rec;
    page_t* page;
    
    lock_type_t type_mode;
    lock_type_t table_lock_type_mode;
};

typedef struct lock_rec lock_rec_t;
struct lock_rec {
    lock_t lock;
    ulint heap_no;
    rec_t* rec;
};

typedef struct lock_table lock_table_t;
struct lock_table {
    lock_t lock;
    dict_table_t* table;
};
```

### 4.2 行锁实现

```c
// storage/innobase/lock/lock0lock.c

dberr_t lock_rec_lock(lock_type_t lock_type, ulint flags,
                     rec_t* rec, page_t* page,
                     mtr_t* mtr)
{
    lock_t* lock;
    dberr_t err;
    
    lock = mem_heap_alloc(lock_heap, sizeof(lock_t));
    if (!lock) {
        return DB_MEM_ALLOC_FAILURE;
    }
    
    lock_init(lock, lock_type, flags);
    lock->rec = rec;
    lock->page = page;
    lock->table_id = page_get_table_id(page);
    lock->index_id = page_get_index_id(page);
    
    // 添加到锁等待队列
    err = lock_rec_insert_lock(lock);
    if (err != DB_SUCCESS) {
        return err;
    }
    
    // 检查是否需要等待
    if (lock_waits(lock)) {
        lock_rec_wait(lock);
    }
    
    return DB_SUCCESS;
}

// 间隙锁
dberr_t lock_gap_lock(lock_type_t lock_type, page_t* page,
                     rec_t* rec, mtr_t* mtr)
{
    lock_t* lock;
    
    lock = mem_heap_alloc(lock_heap, sizeof(lock_t));
    lock_init(lock, lock_type, LOCK_GAP);
    lock->rec = rec;
    lock->page = page;
    
    return lock_rec_insert_lock(lock);
}
```

### 4.3 死锁检测

```c
// storage/innobase/lock/lock0lock.c

dberr_t lock_deadlock_detect(ut_ad_list_t* wait_for_graph)
{
    // 构建等待图
    ut_list_t* nodes = ut_list_create();
    ut_list_t* edges = ut_list_create();
    
    // 遍历所有锁等待
    for (lock_t* lock = ut_list_first(wait_for_graph);
         lock != NULL;
         lock = ut_list_next(lock)) {
        
        lock_t* waiter = lock_get_waiter(lock);
        if (waiter) {
            ut_list_add(edges, lock, waiter);
        }
    }
    
    // DFS 检测环
    if (dfs_detect_cycle(nodes, edges)) {
        // 找到死锁，选择 victim
        lock_t* victim = lock_select_victim(nodes, edges);
        lock_force_rollback(victim);
        return DB_DEADLOCK;
    }
    
    return DB_SUCCESS;
}

static bool dfs_detect_cycle(ut_list_t* nodes, ut_list_t* edges)
{
    color_t* colors = calloc(nodes->size, sizeof(color_t));
    
    for (ut_list_node_t* node = nodes->head; node; node = node->next) {
        if (colors[node->id] == WHITE) {
            if (dfs_visit(node, colors, edges)) {
                return true;
            }
        }
    }
    
    free(colors);
    return false;
}
```

---

## 5. 性能优化实战

### 5.1 Buffer Pool 调优

```sql
-- 查看当前配置
SHOW VARIABLES LIKE 'innodb_buffer_pool%';

-- 推荐配置
SET GLOBAL innodb_buffer_pool_size = _physical_memory * 0.8;
SET GLOBAL innodb_buffer_pool_instances = 8;

-- 监控命中率
SELECT 
    (1 - pages.data / (pages.read + pages.write)) * 100 AS hit_rate
FROM (
    SELECT 
        SUM(pages_read) AS read,
        SUM(pages_written) AS write,
        SUM(pages_data) AS data
    FROM information_schema.innodb_buffer_pool_stats
) pages;
```

### 5.2 日志优化

```sql
-- redo log 配置
SET GLOBAL innodb_log_file_size = 1G;
SET GLOBAL innodb_log_files_in_group = 2;
SET GLOBAL innodb_flush_log_at_trx_commit = 2;  -- 性能优化

-- binlog 配置
SET GLOBAL sync_binlog = 1000;  -- 平衡性能与安全性
SET GLOBAL binlog_format = 'ROW';
```

### 5.3 索引优化

```sql
-- 慢查询分析
SELECT 
    query_time,
    lock_time,
    rows_sent,
    rows_examined,
    sql_text
FROM performance_schema.events_statements_history
WHERE query_time > INTERVAL 1 SECOND
ORDER BY query_time DESC
LIMIT 10;

-- 索引使用情况
SELECT 
    table_name,
    index_name,
    count_star,
    count_read,
    count_write
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE count_star > 0
ORDER BY count_star DESC;
```

---

## 6. 排查案例

### 6.1 死锁排查

```sql
-- 查看死锁信息
SHOW ENGINE INNODB STATUS\G

-- 分析输出
------------------------
LATEST DETECTED DEADLOCK
------------------------
*** (1) TRANSACTION:
TRANSACTION 12345, ACTIVE 0 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 3 lock struct(s), heap size 1184, 2 row lock(s)
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 1234 page no 567 n bits 72 index PRIMARY
*** (2) TRANSACTION:
TRANSACTION 12346, ACTIVE 0 sec starting index read
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1184, 2 row lock(s)
*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 1234 page no 567 n bits 72 index PRIMARY
```

**解决方案**：
```sql
-- 调整事务顺序，统一锁获取顺序
-- 或使用 SELECT ... FOR UPDATE NOWAIT
```

### 6.2 锁等待排查

```sql
-- 查看锁等待
SELECT 
    r.trx_id waiting_trx_id,
    r.trx_mysql_thread_id waiting_thread,
    r.trx_query waiting_query,
    b.trx_id blocking_trx_id,
    b.trx_mysql_thread_id blocking_thread,
    b.trx_query blocking_query
FROM information_schema.innodb_lock_waits w
JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id;
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 | 关键优化点 |
|------|----------|-----------|
| 事务 | MVCC + Undo Log | 读视图优化、Undo 空间回收 |
| 索引 | B+ 树 | 页分裂策略、索引选择 |
| 锁 | 行锁 + 间隙锁 | 死锁检测、锁等待超时 |
| 缓冲 | Buffer Pool | 命中率、淘汰算法 |

### 7.2 性能调优 Checklist

- [ ] 设置合适的 Buffer Pool 大小
- [ ] 优化 Redo Log 配置
- [ ] 合理使用索引
- [ ] 监控锁等待和死锁
- [ ] 调整 Innodb Flush 策略
- [ ] 定期分析慢查询

---

*最后更新：2026-08-11*
*作者：Ryan*
