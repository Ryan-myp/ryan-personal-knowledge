# MySQL InnoDB 源码级深度：事务/锁/MVCC/B+ Tree

> 逐行分析 InnoDB 事务引擎、锁机制和索引结构

---

## 第一部分：事务源码深度

### 事务状态机

```
事务生命周期：
IDLE → ACTIVE → LOCK_WAIT → TRX_PREPARED → COMMITTED/ROLLED_BACK

源码实现（trx0trx.cc）：

enum trx_state_t {
  TRX_STATE_NOT_STARTED,  // 未开始
  TRX_STATE_ACTIVE,       // 活跃中（执行 SQL）
  TRX_STATE_LOCK_WAIT,    // 等待锁
  TRX_STATE_PREPARED,     // 已准备（二阶段提交）
  TRX_STATE_COMMITTED_IN_MEMORY,  // 内存中已提交
  TRX_STATE_COMMITTED,    // 已提交（持久化）
  TRX_STATE_ROLLING_BACK, // 回滚中
  TRX_STATE_ROLLBACK_DONE // 回滚完成
};
```

### 源码逐行解析：trx_commit

```c
// InnoDB 源码：trx0trx.cc - trx_commit
// 提交事务：写 Redo Log + 更新事务状态 + 释放锁

void
trx_commit(trx_t* trx)
{
  // 1. 设置事务状态为 PREPARED
  trx->state = TRX_STATE_PREPARED;
  
  // 2. 写 Redo Log（COMMIT 记录）
  lsn_t commit_lsn = log_write_commit(trx);
  
  // 3. fsync Redo Log 确保持久化
  log_flush_up_to(commit_lsn);
  
  // 4. 更新事务槽（trx_sys->trx_rseg_holds）
  ulint   slot = trx_get_slot(trx);
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

**关键点**：
- **先写 Redo Log 再释放锁**：保证崩溃恢复时能重做提交
- **commit_event**：等待该事务的其他线程被唤醒

### 两阶段提交（2PC）

```c
// 分布式事务的两阶段提交

// Phase 1: Prepare
void trx_prepare(trx_t* trx) {
  // 1. 写 prepare Redo Log
  log_write_prepare(trx);
  
  // 2. fsync 确保持久化
  log_flush();
  
  // 3. 标记事务为 prepared
  trx->state = TRX_STATE_PREPARED;
}

// Phase 2: Commit
void trx_commit_phase2(trx_t* trx) {
  // 1. 所有参与者确认
  if (all_participants_ack()) {
    // 2. 写 commit Redo Log
    log_write_commit(trx);
    log_flush();
    // 3. 释放锁
    lock_release(trx);
  } else {
    // 回滚
    trx_rollback(trx);
  }
}
```

---

## 第二部分：锁机制源码深度

### 锁类型

```
InnoDB 锁层次：
├── 全局锁（Global Lock）：FLUSH TABLES WITH READ LOCK
├── 表级锁（Table Lock）：LOCK TABLES / MDL
├── 行级锁（Row Lock）：Record Lock / Gap Lock / Next-Key Lock
└── 意向锁（Intention Lock）：IS / IX（表级，用于锁兼容检查）
```

### 源码逐行解析：lock_rec_lock

```c
// InnoDB 源码：lock0lock.cc - lock_rec_lock
// 给记录加锁

lock_wait_status_t
lock_rec_lock(
  ulint       mode,       // 锁模式（S/X）
  dtuple_t*       tuple,      // 锁定的记录
  que_thr_t*      thr,        // 当前线程
  mem_heap_t*   heap)     // 内存堆
{
  // 1. 查找记录所在的页
  buf_block_t*  block = lock_rec_find_block(tuple);
  rec_t*    rec = lock_rec_find_rec(block, tuple);
  
  // 2. 检查锁是否已存在
  lock_t* existing_lock = lock_rec_get(lock, rec);
  if (existing_lock != NULL) {
    // 2.1 锁兼容检查
    if (lock_is_compatible(existing_lock->mode, mode)) {
      return(LOCK_WAIT_GRANTED);  // 兼容，直接授予
    }
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

### Next-Key Lock 原理

```
Next-Key Lock = Record Lock + Gap Lock

记录在 B+ Tree 中的位置：
... 10 | 20 | 30 | 40 ...

Record Lock: 锁定具体记录（如 20）
Gap Lock:  锁定间隙（如 10-20 之间）
Next-Key Lock: 锁定记录和间隙（如 (10, 20]）

为什么需要 Gap Lock？
防止幻读！
- 事务 A 查询 WHERE id > 20 FOR UPDATE
- 事务 B 插入 id=25（被 Next-Key Lock 阻止）
- 如果没有 Gap Lock，事务 B 可以插入，造成幻读
```

---

## 第三部分：MVCC 源码深度

### Read View 结构

```c
// InnoDB 源码：trx0sys.h - read_view_t
struct read_view_t {
  // 创建 Read View 时活跃的事务 ID 列表
  ulint*        down_trx_id;
  ulint         n_down_ids;
  
  // 最小活跃事务 ID
  ulint         min_trx_id;
  
  // 最大活跃事务 ID
  ulint         max_trx_id;
  
  // 创建 Read View 后分配的下一个事务 ID
  ulint         creator_trx_id;
  
  // 是否可见性检查完成
  bool          ready;
};
```

### 源码逐行解析：read_view_sees_trx_id

```c
// InnoDB 源码：trx0sys.cc - read_view_sees_trx_id
// 判断 Read View 是否能看到某个事务的修改

bool
read_view_sees_trx_id(
  const read_view_t* view,
  ulint       trx_id)
{
  // 1. 事务还没开始 → 可见
  if (trx_id < view->min_trx_id) {
    return(true);
  }
  
  // 2. 事务已提交 → 可见
  if (trx_id >= view->max_trx_id) {
    return(true);
  }
  
  // 3. 是当前事务创建的 Read View → 可见
  if (trx_id == view->creator_trx_id) {
    return(true);
  }
  
  // 4. 在活跃事务列表中 → 不可见
  for (ulint i = 0; i < view->n_down_ids; i++) {
    if (view->down_trx_ids[i] == trx_id) {
      return(false);
    }
  }
  
  // 5. 不在活跃列表中，说明已提交 → 可见
  return(true);
}
```

**RC vs RR 的区别**：
- **RC（读已提交）**：每次 SELECT 创建新的 Read View
- **RR（可重复读）**：事务中第一次 SELECT 创建 Read View，后续复用

---

## 第四部分：B+ Tree 索引源码深度

### B+ Tree 结构

```
B+ Tree vs B Tree:

B Tree:
  每个节点都存数据
  树的高度 = 查询的 IO 次数

B+ Tree:
  只有叶子节点存数据
  非叶子节点只存索引（键值 + 指针）
  叶子节点用链表连接（范围查询友好）

InnoDB B+ Tree 示例：
┌─────────────────────────────────────────────┐
│  根节点（非叶子）                              │
│  [10, 20, 30]                                │
│  ↓    ↓    ↓    ↓                            │
│  P1   P2   P3   P4                           │
├─────────────────────────────────────────────┤
│  叶子节点（存数据）                            │
│  [1|data] [5|data] [10|data] [15|data]       │
│  [20|data] [25|data] [30|data] [35|data]     │
│  ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←← │
│              叶子链表（范围查询）                │
└─────────────────────────────────────────────┘
```

### 源码逐行解析：btr_cur_search_to_nth_level

```c
// InnoDB 源码：btr0cur.cc - btr_cur_search_to_nth_level
// 在 B+ Tree 中搜索指定深度的页

btr_cur_t*
btr_cur_search_to_nth_level(
  buf_block_t*    root,       // 根节点
  ulint       level,        // 目标层数（0=叶子）
  const dtuple_t*   tuple,      // 搜索元组
  ulint       mode,       // 锁模式
  btr_cur_t*    cursor,     // 输出游标
  mem_heap_t*   heap)     // 内存堆
{
  // 1. 从根节点开始，逐层向下搜索
  buf_block_t*  block = root;
  ulint   current_level = btr_block_get_level(block);
  
  while (current_level > level) {
    // 2. 在当前节点二分查找
    rec_t*    rec = btr_node_search(block, tuple);
    
    // 3. 跟随指针到下一层
    page_no_t page_no = rec_get_page_ptr(rec);
    block = buf_page_get(page_id_t(space_id, page_no), RW_S_LATCH);
    
    // 4. 更新当前层数
    current_level = btr_block_get_level(block);
  }
  
  // 5. 到达目标层，设置游标
  cursor->block = block;
  cursor->rec = rec;
  cursor->index = index;
  cursor->mode = mode;
  
  return(cursor);
}
```

### 索引合并（Index Merge）

```
当查询条件有多个索引时，InnoDB 可以选择：

1.  Union:   取多个索引结果的并集
2.  Intersect: 取多个索引结果的交集
3.  Sort_union: 先排序再取并集

示例：
SELECT * FROM users WHERE age=25 OR city='Beijing';
→ Index Merge Union:
  - 用 age 索引找到 age=25 的记录
  - 用 city 索引找到 city='Beijing' 的记录
  - 合并去重

EXPLAIN 输出：
Extra: Using union(age_idx,city_idx); Using temporary
```

---

## 第五部分：自测题

### Q1: RC 和 RR 的幻读区别？

**A**:
- **RC**：每次 SELECT 创建新 Read View，可能看到不同快照 → 有幻读
- **RR**：事务中复用第一个 Read View，快照一致 → 无幻读
- 但 RR 仍有间隙锁导致的幻读（FOR UPDATE/LOCK IN SHARE MODE）

### Q2: 聚簇索引和非聚簇索引的区别？

**A**:
- **聚簇索引**：叶子节点存整行数据，InnoDB 主键就是聚簇索引
- **非聚簇索引**（二级索引）：叶子节点存主键值，查数据需要回表
- **覆盖索引**：查询的列都在二级索引中，不需要回表

### Q3: 如何优化慢查询？

**A**:
1. EXPLAIN 分析执行计划
2. 检查是否用到索引（type=ALL 说明全表扫描）
3. 最左前缀原则（联合索引）
4. 避免在索引列上做函数运算
5. 减少回表（使用覆盖索引）
6. 分页优化（延迟关联）
