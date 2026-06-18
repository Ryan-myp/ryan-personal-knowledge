# MySQL InnoDB 深度：Buffer Pool/Redo Log/Undo Log 源码级

> 逐行分析 InnoDB 核心组件源码，理解数据库如何保证 ACID

---

## 第一部分：Buffer Pool 源码深度

### Buffer Pool 架构

```
Buffer Pool 组成：
├── Page Hash Table  （哈希索引，O(1) 查找页）
├── LRU List          （最近最少使用链表）
│   ├── Young Half    （新半区：新页面）
│   └── Old Half      （旧半区：可能被换出）
├── Free List         （空闲页链表）
├── Flush List         （脏页链表，按 LSN 排序）
└── Insert Buffer      （二级索引变更合并写入）
```

### buf_pool_init 源码逐行解析

```c
// InnoDB 源码：buf0buf.cc - buf_pool_init
ulint buf_pool_init(ulint pool_size, ulint n_threads) {
    ulint i;
    ulint page_size = srv_page_size;
    ulint n_pages = pool_size / page_size;
    
    for (i = 0; i < n_threads; i++) {
        buf_pool_t *buf_pool = ut_malloc_no_keys(sizeof(*buf_pool));
        
        // 1. 分配页内存
        buf_pool->frame_size = page_size;
        buf_pool->n_frames = n_pages / n_threads;
        buf_pool->frames = ut_malloc_no_keys(
            buf_pool->n_frames * page_size);
        
        // 2. 初始化 LRU 链表
        UT_LIST_INIT(buf_pool->LRU);
        UT_LIST_INIT(buf_pool->flush_list);
        UT_LIST_INIT(buf_pool->free);
        
        // 3. 初始化哈希表
        buf_pool->hash_size = buf_pool->n_frames / 2;
        buf_pool->hash_tables = ut_malloc_no_keys(
            buf_pool->hash_size * sizeof(hash_table_t));
        
        // 4. 初始化互斥锁
        os_thread_create(buf_pool_page_zip_free, buf_pool);
    }
    
    return(0);
}
```

**关键点**：
- **每个线程一个 buf_pool 实例**：避免锁竞争
- **LRU 链表分新旧两半**：防止全表扫描冲刷掉热点页
- **哈希表大小 = 帧数/2**：负载因子 0.5，减少碰撞

### buf_page_get_gen 源码逐行解析

```c
// InnoDB 源码：buf0buf.cc - buf_page_get_gen
buf_block_t* buf_page_get_gen(
    const page_id_t& page_id,
    const page_size_t& page_size,
    ulint rw_lock_mode,
    const page_cur_t* searcher,
    ulint flag,
    const char* file,
    ulint line,
    mtr_t* mtr) {
    
    buf_block_t* block;
    ulint tries = 0;
    
    // 1. 哈希表查找页
    block = buf_page_hash_get_low(page_id, page_size, RW_LOCK_S);
    
    if (block != NULL) {
        // 1.1 命中 Buffer Pool
        buf_page_invalidate_hash(block);
        buf_page_set_accessed(block);  // 标记为访问过
        
        // 1.2 移动到 LRU 链表头部
        buf_LRU_block_remove(block);
        buf_LRU_block_add_first(block);
        
        // 1.3 加锁并返回
        buf_page_get_LRW(block, rw_lock_mode, file, line);
        return(block);
    }
    
    // 2. 未命中：从磁盘读取
    block = buf_page_get_io(page_id, page_size, flag, mtr);
    
    // 3. 等待 I/O 完成
    while (!buf_page_is_compressed(block)
       && !buf_page_is_flush_lru(block)) {
        os_event_wait(buf_pool->event);
        tries++;
    }
    
    return(block);
}
```

---

## 第二部分：Redo Log 源码深度

### Redo Log 架构

```
Redo Log 组成：
├── Log Buffer      （内存中的日志缓冲区，16MB 默认）
├── Log File        （磁盘上的日志文件，2 个循环写入）
│   ├── ib_logfile0
│   └── ib_logfile1
└── Checkpoint      （LSN 检查点，标记已刷盘位置）

写入流程（WAL 机制）：
1. 修改 Buffer Pool 中的页（内存修改）
2. 生成 Redo Log 写入 Log Buffer
3. 事务提交时刷盘 Log Buffer → Log File（fsync）
4. 后台线程刷新脏页 → 数据文件（异步）

关键：先写日志，再写数据！
```

### log_write_up_to 源码逐行解析

```c
// InnoDB 源码：log0log.cc - log_write_up_to
void log_write_up_to(lsn_t target_lsn, bool flush_last_chunk) {
    lsn_t bytes_to_write = target_lsn - log_sys->lsn;
    
    if (bytes_to_write == 0)
        return;  // 没有新日志，直接返回
    
    // 1. 检查 Log Buffer 是否已满
    if (log_sys->write_size >= LOG_BUFFER_SIZE)
        log_write_buf();
    
    // 2. 分块刷写（避免一次性 fsync 太多数据）
    ulint chunk_size = std::min(bytes_to_write, LOG_WRITE_CHUNK_SIZE);
    ulint n_chunks = (bytes_to_write + chunk_size - 1) / chunk_size;
    
    for (ulint i = 0; i < n_chunks; i++) {
        // 2.1 拷贝 Log Buffer 到临时缓冲区
        byte* src = log_sys->buffer + log_sys->write;
        ulint size = std::min(chunk_size, bytes_to_write);
        
        // 2.2 写入磁盘（O_DIRECT 绕过 Page Cache）
        os_file_write(log_sys->files[i % 2].file, src, size, log_sys->write_pos);
        
        // 2.3 fsync 确保数据落盘
        os_file_flush(log_sys->files[i % 2].file);
        
        // 2.4 更新 LSN
        log_sys->lsn += size;
        log_sys->write += size;
        bytes_to_write -= size;
    }
    
    // 3. 如果是最后一个 chunk，确保持久化
    if (flush_last_chunk)
        os_file_flush_all();
}
```

---

## 第三部分：Undo Log 源码深度

### Undo Log 架构

```
Undo Log 组成：
├── Undo Log Header   （事务信息：trx_id, prev_trx）
├── Undo Log Record   （实际的回滚数据）
│   ├── Insert Undo   （INSERT 操作的逆操作：删除）
│   └── Update Undo   （UPDATE/DELETE 的逆操作：恢复）
└── Undo Log Chain    （事务链：prev_trx 链接）

用途：
1. MVCC：为其他事务提供历史版本
2. 回滚：事务失败时恢复到之前状态
3. 快照读：Read View 读取 undo log 中的旧版本
```

### trx_undo_prev_version_build 源码逐行解析

```c
// InnoDB 源码：trx0rec.cc - trx_undo_prev_version_build
dberr_t trx_undo_prev_version_build(
    dtuple_t* tuple,
    buf_block_t* block,
    rec_t* rec,
    const mtr_t* mtr) {
    
    ulint undo_log_ptr = rec_get_undo_log(rec);
    if (undo_log_ptr == 0)
        return(DB_UNSUPPORTED);  // 没有 undo log
    
    // 1. 解析 undo log header
    trx_id_t prev_trx_id = mach_read_from_8(
        undo_ptr + TR_UNDO_LOG_TRX_ID);
    
    // 2. 获取 undo log record
    undo_rec_t* undo_rec = undo_log_get_rec(undo_ptr);
    
    // 3. 根据 undo 类型构建旧版本
    ulint type = undo_rec_get_type(undo_rec);
    
    switch (type) {
        case TRX_UNDO_INSERT_REC:
            // INSERT 的 undo：删除该记录
            break;
            
        case TRX_UNDO_UPDATE_DEL:
            // UPDATE 的 undo：删除操作
            ptr = undo_rec_get_data(undo_rec);
            rec_build_old_rec(tuple, block, ptr, offset_heap);
            break;
            
        case TRX_UNDO_DEL_MARK_REC:
            // DELETE 的 undo：取消删除标记
            rec_build_visible_rec(tuple, block, undo_rec);
            break;
    }
    
    // 4. 更新事务链
    trx_id_t prev_trx = mach_read_from_8(
        undo_ptr + TR_UNDO_LOG_PREV_TRX);
    
    return(DB_SUCCESS);
}
```

---

## 第四部分：事务/锁/MVCC 源码深度

### 源码逐行解析：trx_commit

```c
// InnoDB 源码：trx0trx.cc - trx_commit
void trx_commit(trx_t* trx) {
    // 1. 设置事务状态为 PREPARED
    trx->state = TRX_STATE_PREPARED;
    
    // 2. 写 Redo Log（COMMIT 记录）
    lsn_t commit_lsn = log_write_commit(trx);
    
    // 3. fsync Redo Log 确保持久化
    log_flush_up_to(commit_lsn);
    
    // 4. 更新事务槽
    ulint slot = trx_get_slot(trx);
    trx_sys->trx_rseg_holds[slot].state = TRX_RSEG_STATE_COMMITTED;
    
    // 5. 释放事务持有的锁
    lock_trx_release_locks(trx);
    
    // 6. 更新 Read View 可见性
    read_view_close(trx->read_view);
    
    // 7. 设置事务状态为 COMMITTED
    trx->state = TRX_STATE_COMMITTED;
    
    // 8. 通知等待该事务的线程
    os_event_set(trx->commit_event);
}
```

### 源码逐行解析：lock_rec_lock

```c
// InnoDB 源码：lock0lock.cc - lock_rec_lock
lock_wait_status_t lock_rec_lock(
    ulint mode,
    dtuple_t* tuple,
    que_thr_t* thr,
    mem_heap_t* heap) {
    
    // 1. 查找记录所在的页
    buf_block_t* block = lock_rec_find_block(tuple);
    rec_t* rec = lock_rec_find_rec(block, tuple);
    
    // 2. 检查锁是否已存在
    lock_t* existing_lock = lock_rec_get(lock, rec);
    if (existing_lock != NULL) {
        // 2.1 锁兼容检查
        if (lock_is_compatible(existing_lock->mode, mode))
            return(LOCK_WAIT_GRANTED);  // 兼容，直接授予
        
        // 2.2 不兼容，加入等待队列
        lock_rec_wait(thr, lock, rec, mode);
        return(LOCK_WAIT_NOT_GRANTED);
    }
    
    // 3. 创建新锁
    lock_t* new_lock = lock_rec_create(block, rec, mode);
    
    // 4. 插入锁哈希表
    lock_hash_insert(new_lock);
    
    // 5. 更新记录上的锁指针
    rec_set_lock_info(rec, new_lock);
    
    return(LOCK_WAIT_GRANTED);
}
```

### MVCC 源码逐行解析：read_view_sees_trx_id

```c
// InnoDB 源码：trx0sys.cc - read_view_sees_trx_id
bool read_view_sees_trx_id(const read_view_t* view, ulint trx_id) {
    // 1. 事务还没开始 → 可见
    if (trx_id < view->min_trx_id)
        return(true);
    
    // 2. 事务已提交 → 可见
    if (trx_id >= view->max_trx_id)
        return(true);
    
    // 3. 是当前事务创建的 Read View → 可见
    if (trx_id == view->creator_trx_id)
        return(true);
    
    // 4. 在活跃事务列表中 → 不可见
    for (ulint i = 0; i < view->n_down_ids; i++) {
        if (view->down_trx_ids[i] == trx_id)
            return(false);
    }
    
    // 5. 不在活跃列表中，说明已提交 → 可见
    return(true);
}
```

---

## 第五部分：自测题

### Q1: Buffer Pool 为什么分新旧两半？

**A**: 防止全表扫描（一次性读取大量页）冲刷掉热点页。新页先进入 Young Half，积累到一定程度后才移入 Old Half。换出时优先从 Old Half 尾部移除，保护 Young Half 中的热点数据。

### Q2: Redo Log 和 Binlog 的区别？

**A**:
| 维度 | Redo Log | Binlog |
|------|---------|--------|
| 级别 | InnoDB 引擎层 | Server 层 |
| 内容 | 物理日志（页修改） | 逻辑日志（SQL 语句） |
| 用途 | 崩溃恢复 | 主从复制/时间点恢复 |
| 大小 | 固定大小（循环写入） | 无限增长 |

### Q3: Undo Log 什么时候释放？

**A**: Undo Log 在事务提交后不会立即释放，而是由 purge 线程异步清理。purge 线程检查是否有其他事务还在引用该 undo log（通过 Read View），如果没有引用才释放。

---

## 第六部分：生产排障

### 1. Buffer Pool 命中率低

```bash
# 检查 Buffer Pool 命中率
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';

# Innodb_buffer_pool_read_requests: 总读取次数
# Innodb_buffer_pool_reads: 从磁盘读取次数

# 命中率 = 1 - reads / read_requests
# 理想值 > 99%

# 解决方案：
# 1. 增加 innodb_buffer_pool_size（建议物理内存的 70-80%）
# 2. 检查是否有全表扫描
# 3. 优化慢查询
```

### 2. Redo Log 频繁刷盘

```bash
# 检查 Redo Log 使用情况
SHOW ENGINE INNODB STATUS\G

# 关键指标：
# Log sequence number: 当前 LSN
# Log flushed up to: 已刷盘 LSN
# 差值越大，积压越多

# 解决方案：
# 1. 增加 innodb_log_file_size（默认 48MB，建议 1-2GB）
# 2. 增加 innodb_log_files_in_group（默认 2）
# 3. 使用 SSD 存储
# 4. 调整 innodb_flush_log_at_trx_commit
```

### 3. Undo Log 膨胀

```bash
# 检查 Undo 表空间使用情况
SELECT * FROM information_schema.INNODB_TRX;

# 检查长事务
SELECT trx_id, trx_started, trx_state, trx_query
FROM information_schema.INNODB_TRX
WHERE trx_started < NOW() - INTERVAL 1 HOUR;

# 解决方案：
# 1. 杀死长事务
# 2. 优化事务，减少事务持续时间
# 3. 增加 undo tablespace 大小
```
