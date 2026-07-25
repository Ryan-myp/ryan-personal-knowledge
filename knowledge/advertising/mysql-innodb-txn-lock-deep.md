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

---

## Go 代码实战：InnoDB 事务锁模拟与排障

### 1. Next-Key Lock 模拟实现

```go
package innodb

import (
	"sync"
)

// Record 数据行记录
type Record struct {
	ID        int64
	Data      string
	TXID      uint64 // 最后修改的事务ID
	DeleteBit bool   // 逻辑删除标记
}

// LockType 锁类型
type LockType int

const (
	LockNone LockType = iota
	LockRecord    // 记录锁
	LockGap       // 间隙锁
	LockNextKey   // 临键锁（记录+间隙）
	LockIntent    // 意向锁
)

// RowLock 行级锁
type RowLock struct {
	RecordID int64
	Type     LockType
	TXID     uint64
	WaitChan chan struct{} // 等待唤醒的channel
}

// LockManager 锁管理器（简化版）
type LockManager struct {
	mu        sync.Mutex
	locks     map[int64]*RowLock // 记录锁
	gapLocks  []GapLock          // 间隙锁
	waitQueue map[uint64][]*RowLock // TXID -> 等待中的锁
}

// GapLock 间隙锁
type GapLock struct {
	LowerBound int64
	UpperBound int64
	TXID       uint64
}

func NewLockManager() *LockManager {
	return &LockManager{
		locks:     make(map[int64]*RowLock),
		waitQueue: make(map[uint64][]*RowLock),
	}
}

// AcquireLock 获取锁（含阻塞等待逻辑）
func (lm *LockManager) AcquireLock(txid uint64, recordID int64, lockType LockType) error {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	
	// 检查是否已持有
	if existing, ok := lm.locks[recordID]; ok && existing.TXID == txid {
		return nil // 同一事务可升级
	}
	
	// 检查是否有冲突锁
	if blocker, ok := lm.locks[recordID]; ok && blocker.TXID != txid {
		// 冲突！加入等待队列
		lm.waitQueue[txid] = append(lm.waitQueue[txid], &RowLock{
			RecordID: recordID,
			Type:     lockType,
			TXID:     txid,
			WaitChan: make(chan struct{}),
		})
		lm.mu.Unlock()
		
		// 阻塞等待
		<-(&RowLock{WaitChan: make(chan struct{})}.WaitChan)
		lm.mu.Lock()
		return nil
	}
	
	// 无冲突，直接加锁
	lm.locks[recordID] = &RowLock{
		RecordID: recordID,
		Type:     lockType,
		TXID:     txid,
	}
	return nil
}

// ReleaseLocks 释放事务持有的所有锁（commit/rollback时调用）
func (lm *LockManager) ReleaseLocks(txid uint64) {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	
	for id, lock := range lm.locks {
		if lock.TXID == txid {
			delete(lm.locks, id)
		}
	}
	
	// 唤醒等待队列中的事务
	for waitTXID, waits := range lm.waitQueue {
		if len(waits) > 0 {
			close(waits[0].WaitChan)
		}
	}
}

// DeadlockDetector 死锁检测（基于等待图DFS）
type DeadlockDetector struct {
	waitForGraph map[uint64]uint64 // waiterTXID -> holderTXID
}

func (d *DeadlockDetector) DetectCycle(waiter, holder uint64) bool {
	d.waitForGraph[waiter] = holder
	
	// DFS 检测环
	visited := make(map[uint64]bool)
	current := holder
	for current != 0 {
		if visited[current] {
			return true // 检测到环 → 死锁
		}
		visited[current] = true
		current = d.waitForGraph[current]
	}
	return false
}
```

### 2. MVCC Read View 实现

```go
package innodb

import (
	"fmt"
	"sort"
)

// ReadView MVCC读视图
type ReadView struct {
	mixTrxID  uint64 // 创建时最小活跃事务ID
	maxTrxID  uint64 // 创建时最大事务ID+1
	cursorTrxID uint64 // 当前事务ID
	trxIDs    []uint64 // 活跃事务ID列表
}

// CreateReadView 创建读视图（RR隔离级别下只创建一次）
func CreateReadView(activeTXIDs []uint64, currentTXID uint64) *ReadView {
	sort.Slice(activeTXIDs, func(i, j int) bool {
		return activeTXIDs[i] < activeTXIDs[j]
	})
	
	minID := activeTXIDs[0]
	maxID := activeTXIDs[len(activeTXIDs)-1] + 1
	
	return &ReadView{
		mixTrxID:    minID,
		maxTrxID:    maxID,
		cursorTrxID: currentTXID,
		trxIDs:      activeTXIDs,
	}
}

// IsVisible 判断记录对当前读视图是否可见
func (rv *ReadView) IsVisible(recordTXID uint64, deleteBit bool) bool {
	// 1. 记录已被当前事务删除 → 不可见
	if deleteBit {
		return false
	}
	
	// 2. 记录由当前事务创建 → 可见
	if recordTXID == rv.cursorTrxID {
		return true
	}
	
	// 3. 记录在ReadView创建前已提交 → 可见
	if recordTXID < rv.mixTrxID {
		return true
	}
	
	// 4. 记录在ReadView创建后才启动 → 不可见
	if recordTXID >= rv.maxTrxID {
		return false
	}
	
	// 5. 记录在活跃列表中 → 未提交，不可见
	for _, txid := range rv.trxIDs {
		if txid == recordTXID {
			return false
		}
	}
	
	return true
}

// UndoLogVersion 回滚版本链节点
type UndoLogVersion struct {
	TXID      uint64
	PrevPtr   *UndoLogVersion
	Record    *Record
	DeleteBit bool
}

// GetLatestVisible 遍历版本链找到第一个可见的版本
func GetLatestVisible(head *UndoLogVersion, view *ReadView) (*Record, error) {
	for v := head; v != nil; v = v.PrevPtr {
		if view.IsVisible(v.TXID, v.DeleteBit) {
			if v.DeleteBit {
				return nil, fmt.Errorf("record deleted")
			}
			return v.Record, nil
		}
	}
	return nil, fmt.Errorf("no visible version found")
}
```

### 自测题

<details>
<summary>Q1: 为什么 InnoDB 的 Next-Key Lock 要同时锁记录和间隙？不用 Record Lock 够吗？</summary>

**答案**：

**问题场景**：假设表中有 ID=1,3,5 三行。事务 A `SELECT * FROM t WHERE id=3 FOR UPDATE` 加了记录锁(3)。此时事务 B `INSERT INTO t VALUES (2,...)` — 如果只有记录锁，B 可以插入 2，然后 C `INSERT INTO t VALUES (4,...)` 也可以插入，造成**幻读**。

**Next-Key Lock = Record Lock + Gap Lock**：
- Record Lock(3)：锁住 ID=3 这行
- Gap Lock(1,3)：锁住 (1,3) 这个区间，阻止插入 2
- Gap Lock(3,5)：锁住 (3,5) 这个区间，阻止插入 4

这样 INSERT 2 和 INSERT 4 都会被阻塞，避免幻读。

</details>

<details>
<summary>Q2: DeadlockDetector 的 DFS 检测死锁在大规模系统中有什么性能问题？如何优化？</summary>

**答案**：

**问题**：
1. DFS O(V+E) 每次都要遍历整个等待图——V=活跃事务数可能上万
2. 每次锁请求都触发检测会严重影响吞吐

**优化方案**：
```go
// 方案1: 按需检测（推荐）
// 只在发生超时等待时才触发检测，而非每次加锁
func (d *DeadlockDetector) detectOnTimeout() {
    // 等待超时后才构建完整等待图并DFS
}

// 方案2: 预检测（预防优于检测）
// 使用拓扑排序提前检测潜在死锁
// 方案3: 随机回退
// 让一个事务随机回滚，打破死锁（简单但不够智能）

// 生产环境：方案1 + 方案3 组合
// 默认不检测（零开销），超时后检测，检测到死锁随机回滚
```

MySQL InnoDB 实际采用：等待图 + 超时检测 + 回滚最小事务（基于 undo log 大小）。

</details>

<details>
<summary>Q3: MVCC 的 ReadView 在 RC 和 RR 隔离级别下有什么区别？为什么 RC 有幻读而 RR 没有？</summary>

**答案**：

| 特性 | RC（读已提交） | RR（可重复读） |
|------|--------------|--------------|
| ReadView 创建时机 | **每次 SELECT 都创建新视图** | 事务中**第一次 SELECT 创建，之后复用** |
| 可见性判断 | 每次都重新评估 | 始终用同一个视图 |
| 幻读 | ✅ 有（新提交的数据对新视图可见） | ❌ 无（旧视图看不到新数据） |
| 一致性非锁定读 | ✅ | ✅ |

**RC 幻读示例**：
```
T1: BEGIN;
T2: INSERT INTO t VALUES (10); COMMIT;
T3: SELECT * FROM t;  -- 看到 ID=10（新ReadView）
T4: SELECT * FROM t;  -- 又看到 ID=10（又一个新ReadView）← 幻读
```

**RR 无幻读**：T3 和 T4 用同一个 ReadView，T2 的 INSERT 在 ReadView 创建后才提交，所以两次都看不到。

</details>
