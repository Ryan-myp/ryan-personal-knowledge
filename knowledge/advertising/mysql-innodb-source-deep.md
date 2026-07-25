# MySQL InnoDB 源码级深度：Buffer Pool/Redo Log/Undo Log

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

内存分布（默认 128MB）：
┌─────────────────────────────────────────────────┐
│ Page Hash Table (1/8)                           │
├─────────────────────────────────────────────────┤
│ LRU List (7/8)                                  │
│  ┌──── Young Half ────┐ ┌── Old Half ──┐       │
│  │ 新页面              │ │ 可能被换出     │       │
│  └────────────────────┘ └──────────────┘       │
├─────────────────────────────────────────────────┤
│ Free List + Flush List                          │
└─────────────────────────────────────────────────┘
```

### 源码逐行解析：buf_pool_init

```c
// InnoDB 源码：buf0buf.cc - buf_pool_init
// 初始化 Buffer Pool，分配内存并创建 LRU 链表

ulint
buf_pool_init(
  ulint   pool_size,    // Buffer Pool 总大小（字节）
  ulint   n_threads)    // 线程数
{
  ulint   i;
  ulint   page_size;
  buf_pool_t  *buf_pool;
  
  // 1. 获取页大小（默认 16KB）
  page_size = srv_page_size;
  
  // 2. 计算总页数
  ulint n_pages = pool_size / page_size;
  
  // 3. 为每个 buf_pool 实例分配内存
  for (i = 0; i < n_threads; i++) {
    buf_pool = static_cast<buf_pool_t*>(
      ut_malloc_no_keys(sizeof(*buf_pool)));
    
    // 3.1 分配页内存
    buf_pool->frame_size = page_size;
    buf_pool->n_frames = n_pages / n_threads;
    
    // 3.2 分配帧数组（每个帧是一个页）
    buf_pool->frames = static_cast<byte*>(
      ut_malloc_no_keys(buf_pool->n_frames * page_size));
    
    // 3.3 初始化 LRU 链表
    UT_LIST_INIT(buf_pool->LRU);
    UT_LIST_INIT(buf_pool->flush_list);
    UT_LIST_INIT(buf_pool->free);
    
    // 3.4 初始化哈希表
    buf_pool->hash_size = buf_pool->n_frames / 2;
    buf_pool->hash_tables = static_cast<hash_table_t*>(
      ut_malloc_no_keys(buf_pool->hash_size * sizeof(hash_table_t)));
    
    // 3.5 初始化互斥锁
    os_thread_create(buf_pool_page_zip_free, buf_pool);
  }
  
  return(0);
}
```

**关键点**：
- **每个线程一个 buf_pool 实例**：避免锁竞争
- **LRU 链表分新旧两半**：防止全表扫描冲刷掉热点页
- **哈希表大小 = 帧数/2**：负载因子 0.5，减少碰撞

### 源码逐行解析：buf_page_get_gen

```c
// InnoDB 源码：buf0buf.cc - buf_page_get_gen
// 获取一个页：先在 Buffer Pool 找，找不到则从磁盘读

buf_block_t*
buf_page_get_gen(
  const page_id_t&    page_id,    // 页 ID（表空间+页号）
  const page_size_t&  page_size,  // 页大小
  ulint       rw_lock_mode,     // 锁模式（S/X）
  const page_cur_t*   searcher,   // 搜索上下文
  ulint       flag,
  const char*   file,
  ulint       line,
  mtr_t*        mtr)
{
  buf_block_t*  block;
  ulint       tries = 0;
  
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

**关键点**：
- **LRU 头部插入**：热点页保持在 Young Half
- **异步 I/O**：磁盘读取不阻塞当前线程
- **event 机制**：I/O 完成后通过 event 唤醒等待线程

### LRU 老化机制

```
LRU 链表操作：

1. 新页插入 → LRU 头部（Young Half）
2. 访问已有页 → 移动到 LRU 头部
3. 脏页刷新 → 从 Flush List 移除
4. 换出页 → 从 LRU 尾部移除

Old Half 的作用：
- 防止全表扫描（一次性读取大量页）冲刷掉热点页
- 新页先在 Young Half 积累
- 当 Young Half 满时，最老的页移到 Old Half
- 换出时优先从 Old Half 尾部移除
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

### 源码逐行解析：log_write_up_to

```c
// InnoDB 源码：log0log.cc - log_write_up_to
// 将 Redo Log 从 log_sys->lsn 刷新到 target_lsn

void
log_write_up_to(
  lsn_t       target_lsn,
  bool        flush_last_chunk)
{
  ulint   chunk_size;
  ulint   n_chunks;
  
  // 1. 计算需要刷写的日志量
  lsn_t   bytes_to_write = target_lsn - log_sys->lsn;
  
  if (bytes_to_write == 0) {
    return;  // 没有新日志，直接返回
  }
  
  // 2. 检查 Log Buffer 是否已满
  if (log_sys->write_size >= LOG_BUFFER_SIZE) {
    log_write_buf();  // 强制刷写
  }
  
  // 3. 分块刷写（避免一次性 fsync 太多数据）
  chunk_size = std::min(bytes_to_write, LOG_WRITE_CHUNK_SIZE);
  n_chunks = (bytes_to_write + chunk_size - 1) / chunk_size;
  
  for (ulint i = 0; i < n_chunks; i++) {
    // 3.1 拷贝 Log Buffer 到临时缓冲区
    byte*   src = log_sys->buffer + log_sys->write;
    ulint   size = std::min(chunk_size, bytes_to_write);
    
    // 3.2 写入磁盘（O_DIRECT 绕过 Page Cache）
    os_file_write(
      log_sys->files[i % 2].file,
      src,
      size,
      log_sys->write_pos);
    
    // 3.3 fsync 确保数据落盘
    os_file_flush(log_sys->files[i % 2].file);
    
    // 3.4 更新 LSN
    log_sys->lsn += size;
    log_sys->write += size;
    bytes_to_write -= size;
  }
  
  // 4. 如果是最后一个 chunk，确保持久化
  if (flush_last_chunk) {
    os_file_flush_all();
  }
}
```

**关键点**：
- **O_DIRECT**：绕过 OS Page Cache，避免双重缓冲
- **分块刷写**：避免 fsync 过多数据导致延迟
- **循环写入**：2 个日志文件循环使用，写满后从头开始

### 刷盘策略

```
innodb_flush_log_at_trx_commit 参数：

值=1（默认，最安全）：
  每个事务提交 → fsync Log Buffer → Log File
  优点：ACID 完全保证
  缺点：性能最差（每次提交都 fsync）

值=0：
  每秒 → fsync Log Buffer → Log File
  优点：性能最好
  缺点：崩溃丢失 1 秒数据

值=2：
  每个事务提交 → 写入 OS Cache（不 fsync）
  每秒 → fsync Log Buffer → Log File
  优点：性能好
  缺点：OS 崩溃可能丢失数据

广告系统推荐：值=1（数据安全第一）
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

存储位置：
- 回滚段（Rollback Segment）
- 系统表空间（ibdata1）或独立表空间
```

### 源码逐行解析：trx_undo_prev_version_build

```c
// InnoDB 源码：trx0rec.cc - trx_undo_prev_version_build
// 从 Undo Log 构建行的前一个版本（MVCC 核心）

dberr_t
trx_undo_prev_version_build(
  dtuple_t*       tuple,      // 输出的元组
  buf_block_t*    block,      // 当前页
  rec_t*      rec,        // 当前记录
  const mtr_t*    mtr)        // mini transaction
{
  ulint       offset_heap[REC_N_HEAP];
  ulint       n_fields;
  byte*       ptr;
  ulint       heap_no;
  
  // 1. 获取记录的 undo log 指针
  ulint undo_log_ptr = rec_get_undo_log(rec);
  if (undo_log_ptr == 0) {
    return(DB_UNSUPPORTED);  // 没有 undo log
  }
  
  // 2. 解析 undo log header
  trx_id_t    prev_trx_id = mach_read_from_8(
    undo_ptr + TR_UNDO_LOG_TRX_ID);
  
  // 3. 获取 undo log record
  undo_rec_t* undo_rec = undo_log_get_rec(undo_ptr);
  
  // 4. 根据 undo 类型构建旧版本
  ulint   type = undo_rec_get_type(undo_rec);
  
  switch (type) {
    case TRX_UNDO_INSERT_REC:
      // INSERT 的 undo：删除该记录
      // 不需要构建旧版本，直接返回
      break;
      
    case TRX_UNDO_UPDATE_DEL:
      // UPDATE 的 undo：删除操作
      // 需要从 undo log 恢复原始记录
      ptr = undo_rec_get_data(undo_rec);
      rec_build_old_rec(tuple, block, ptr, offset_heap);
      break;
      
    case TRX_UNDO_DEL_MARK_REC:
      // DELETE 的 undo：取消删除标记
      // 恢复记录的可见性
      rec_build_visible_rec(tuple, block, undo_rec);
      break;
  }
  
  // 5. 更新事务链
  trx_id_t    prev_trx = mach_read_from_8(
    undo_ptr + TR_UNDO_LOG_PREV_TRX);
  
  return(DB_SUCCESS);
}
```

**关键点**：
- **Undo Log 类型**：INSERT/UPDATE_DEL/DEL_MARK 三种
- **MVCC 核心**：通过 undo log 构建历史版本
- **事务链**：prev_trx 链接所有相关事务

### MVCC 实现原理

```
MVCC（多版本并发控制）：

读未提交（RU）：
  Read View.active_trx_ids = 所有活跃事务
  → 能看到所有事务的修改（包括未提交的）

读已提交（RC）：
  Read View.active_trx_ids = 查询开始时活跃的事务
  → 只能看到已提交的事务，但不看到之后的
  
可重复读（RR）：
  Read View.active_trx_ids = 第一个事务开启时活跃的事务
  → 整个事务期间看到相同的快照

幻读解决（RR）：
  第一次查询创建 Read View
  后续查询复用同一个 Read View
  → 看到相同的数据快照
```

---

## 第四部分：自测题

### Q1: Buffer Pool 为什么分新旧两半？

**A**: 防止全表扫描（一次性读取大量页）冲刷掉热点页。新页先进入 Young Half，积累到一定程度后才移入 Old Half。换出时优先从 Old Half 尾部移除，保护 Young Half 中的热点数据。

### Q2: Redo Log 和 Binlog 的区别？

**A**:
| 维度 | Redo Log | Binlog |
|------|---------|--------|
| **级别** | InnoDB 引擎层 | Server 层 |
| **内容** | 物理日志（页修改） | 逻辑日志（SQL 语句） |
| **用途** | 崩溃恢复 | 主从复制/时间点恢复 |
| **大小** | 固定大小（循环写入） | 无限增长 |
| **刷盘时机** | 事务提交时 | 由 binlog_group_commit_sync_no_count_interval 控制 |

### Q3: Undo Log 什么时候释放？

**A**: Undo Log 在事务提交后不会立即释放，而是由 purge 线程异步清理。purge 线程检查是否有其他事务还在引用该 undo log（通过 Read View），如果没有引用才释放。

---

## 第五部分：生产排障

### 1. Buffer Pool 命中率低

```sql
-- 检查 Buffer Pool 命中率
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';

-- Innodb_buffer_pool_read_requests: 总读取次数
-- Innodb_buffer_pool_reads: 从磁盘读取次数

-- 命中率 = 1 - reads / read_requests
-- 理想值 > 99%

-- 解决方案：
-- 1. 增加 innodb_buffer_pool_size（建议物理内存的 70-80%）
-- 2. 检查是否有全表扫描
-- 3. 优化慢查询
```

### 2. Redo Log 频繁刷盘

```sql
-- 检查 Redo Log 使用情况
SHOW ENGINE INNODB STATUS\G

-- 关键指标：
-- Log sequence number: 当前 LSN
-- Log flushed up to: 已刷盘 LSN
-- 差值越大，积压越多

-- 解决方案：
-- 1. 增加 innodb_log_file_size（默认 48MB，建议 1-2GB）
-- 2. 增加 innodb_log_files_in_group（默认 2）
-- 3. 使用 SSD 存储
-- 4. 调整 innodb_flush_log_at_trx_commit
```

### 3. Undo Log 膨胀

```sql
-- 检查 Undo 表空间使用情况
SELECT * FROM information_schema.INNODB_TRX;

-- 检查长事务
SELECT trx_id, trx_started, trx_state, trx_query
FROM information_schema.INNODB_TRX
WHERE trx_started < NOW() - INTERVAL 1 HOUR;

-- 解决方案：
-- 1. 杀死长事务
-- 2. 优化事务，减少事务持续时间
-- 3. 增加 undo tablespace 大小
```

---

## Go 代码实战：InnoDB Buffer Pool 与 Redo Log 模拟

### 1. Buffer Pool 实现（LRU + Flush List）

```go
package innodb

import (
	"sync"
	"time"
)

const (
	PageDefaultSize = 16 * 1024 // 16KB
	BufferPoolSize  = 1024      // 默认1024页
)

// Page 内存页
type Page struct {
	ID       uint64 // page_id
	Data     []byte // 页数据（16KB）
	LSN      uint64 // 最后修改的LSN
	Dirty    bool   // 脏页标记
	FlushLST uint64 // flush_list 中的位置
	LSN      uint64
	Free     bool
}

func NewPage(id uint64) *Page {
	return &Page{
		ID:   id,
		Data: make([]byte, PageDefaultSize),
		Free: true,
	}
}

// LRUList 双向链表实现的LRU
type LRUList struct {
	head *node
	tail *node
	size int
	mu   sync.Mutex
}

type node struct {
	page *Page
	prev *node
	next *node
}

func (l *LRUList) AddToFront(p *Page) {
	l.mu.Lock()
	defer l.mu.Unlock()
	
	n := &node{page: p}
	if l.head == nil {
		l.head = n
		l.tail = n
	} else {
		n.next = l.head
		l.head.prev = n
		l.head = n
	}
	l.size++
}

func (l *LRUList) MoveToFront(n *node) {
	if n == l.head {
		return // 已在头部
	}
	// 从当前位置移除
	if n.prev != nil {
		n.prev.next = n.next
	}
	if n.next != nil {
		n.next.prev = n.prev
	} else {
		l.tail = n.prev
	}
	// 移到头部
	n.prev = nil
	n.next = l.head
	if l.head != nil {
		l.head.prev = n
	}
	l.head = n
	if l.tail == nil {
		l.tail = n
	}
}

func (l *LRUList) RemoveLast() *Page {
	l.mu.Lock()
	defer l.mu.Unlock()
	
	if l.tail == nil {
		return nil
	}
	
	page := l.tail.page
	l.tail = l.tail.prev
	if l.tail != nil {
		l.tail.next = nil
	} else {
		l.head = nil
	}
	l.size--
	return page
}

// BufferPool 缓冲池核心
type BufferPool struct {
	pages      map[uint64]*Page // page_id -> page
	lru        *LRUList
	flushList  []*Page          // 脏页链表
	poolSize   int
	freeList   []*Page
	mu         sync.Mutex
}

func NewBufferPool(size int) *BufferPool {
	pool := &BufferPool{
		pages:    make(map[uint64]*Page),
		lru:      &LRUList{},
		flushList: make([]*Page, 0),
		poolSize: size,
		freeList: make([]*Page, 0, size),
	}
	
	// 预分配页面
	for i := 0; i < size; i++ {
		pool.freeList = append(pool.freeList, NewPage(uint64(i)))
	}
	
	return pool
}

// GetPage 获取页面（含换入逻辑）
func (bp *BufferPool) GetPage(pageID uint64) (*Page, error) {
	bp.mu.Lock()
	defer bp.mu.Unlock()
	
	// 1. 检查是否在池中
	if page, ok := bp.pages[pageID]; ok {
		bp.lru.MoveToFront(&node{page: page})
		return page, nil
	}
	
	// 2. 池满，淘汰LRU末尾
	if len(bp.pages) >= bp.poolSize {
		evicted := bp.lru.RemoveLast()
		if evicted != nil {
			delete(bp.pages, evicted.ID)
			bp.freeList = append(bp.freeList, evicted)
			
			// 如果是脏页，加入flush list
			if evicted.Dirty {
				bp.flushList = append(bp.flushList, evicted)
			}
		}
	}
	
	// 3. 创建新页面或从free list取
	var page *Page
	if len(bp.freeList) > 0 {
		page = bp.freeList[len(bp.freeList)-1]
		bp.freeList = bp.freeList[:len(bp.freeList)-1]
	} else {
		page = NewPage(pageID)
	}
	
	page.ID = pageID
	page.Free = false
	bp.pages[pageID] = page
	bp.lru.AddToFront(page)
	
	return page, nil
}

// MarkDirty 标记脏页
func (bp *BufferPool) MarkDirty(page *Page) {
	page.Dirty = true
	// 加入flush list（如果不在）
	for _, p := range bp.flushList {
		if p.ID == page.ID {
			return
		}
	}
	bp.flushList = append(bp.flushList, page)
}

// Checkpoint 检查点（刷脏页到磁盘）
func (bp *BufferPool) Checkpoint(targetLSN uint64) int {
	bp.mu.Lock()
	defer bp.mu.Unlock()
	
	brushed := 0
	for _, page := range bp.flushList {
		if page.LSN >= targetLSN {
			break
		}
		
		// 写入磁盘（简化）
		bp.writePageToDisk(page)
		page.Dirty = false
		brushed++
	}
	
	// 清理已刷的脏页
	cleaned := make([]*Page, 0)
	for _, page := range bp.flushList {
		if page.Dirty {
			cleaned = append(cleaned, page)
		}
	}
	bp.flushList = cleaned
	
	return brushed
}

func (bp *BufferPool) writePageToDisk(page *Page) {
	// 实际实现：syscall.Write(fd, page.Data, page.ID)
	_ = page
}
```

### 2. Redo Log 实现

```go
package innodb

import (
	"encoding/binary"
	"os"
	"sync"
)

const (
	RedoLogSize      = 256 * 1024 * 1024 // 256MB
	RedoLogBlockSize = 512               // 512字节
)

// RedoLog 重做日志
type RedoLog struct {
	mu        sync.Mutex
	file      *os.File
	writePos  uint64 // 当前写入位置
	checkPoint uint64 // 检查点位置
	buffer    []byte // 内存缓冲
	written   uint64 // 已写入字节数
}

func NewRedoLog(path string) (*RedoLog, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0644)
	if err != nil {
		return nil, err
	}
	
	return &RedoLog{
		file:   f,
		buffer: make([]byte, RedoLogBlockSize),
	}, nil
}

// WriteRedoLog 写入重做日志
func (rl *RedoLog) WriteRedoLog(pageID uint64, offset uint32, data []byte) error {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	
	// 环形缓冲区检查
	if rl.writePos >= RedoLogSize {
		rl.writePos = 0 // 回绕
	}
	
	// 构建redo记录
	rec := &RedoRecord{
		PageID:  pageID,
		Offset:  offset,
		Data:    data,
		LSN:     rl.written,
		Checksum: rl.checksum(data),
	}
	
	// 写入内存buffer
	binary.LittleEndian.PutUint64(rl.buffer[0:8], rec.PageID)
	binary.LittleEndian.PutUint32(rl.buffer[8:12], rec.Offset)
	copy(rl.buffer[12:12+len(rec.Data)], rec.Data)
	
	// 刷盘策略：writethrough（每次fsync）
	_, err := rl.file.WriteAt(rl.buffer[0:len(rl.buffer)], int64(rl.writePos))
	if err != nil {
		return err
	}
	
	rl.file.Sync() // fsync
	rl.writePos += RedoLogBlockSize
	rl.written += uint64(len(rl.buffer))
	
	return nil
}

// RedoRecord 重做记录格式
type RedoRecord struct {
	PageID  uint64
	Offset  uint32
	Data    []byte
	LSN     uint64
	Checksum uint32
}

func (rl *RedoLog) checksum(data []byte) uint32 {
	// CRC32校验
	table := crc32.MakeTable(crc32.IEEE)
	return crc32.Checksum(data, table)
}

// Recover 崩溃恢复（Redo + Undo）
func (rl *RedoLog) Recover(checkpointLSN uint64) ([]*RedoRecord, error) {
	records := make([]*RedoRecord, 0)
	
	// 1. 从checkpointLSN开始扫描redo log
	pos := checkpointLSN % RedoLogSize
	for pos < rl.written {
		rec, err := rl.readRecord(pos)
		if err != nil {
			break
		}
		records = append(records, rec)
		pos += RedoLogBlockSize
	}
	
	// 2. 按LSN排序
	sort.Slice(records, func(i, j int) bool {
		return records[i].LSN < records[j].LSN
	})
	
	// 3. Redo: 重做已提交事务的修改
	// 4. Undo: 回滚未提交事务
	// ... 恢复逻辑
	
	return records, nil
}
```

### 自测题

<details>
<summary>Q1: Buffer Pool 的 Dirty Page 什么时候刷盘？WAL机制为什么能提升10-100倍性能？</summary>

**答案**：

**刷盘触发条件**：
1. **Checkpoint**：当 redo log 快满了（写满75%），强制刷脏页
2. **空闲页面不足**：需要新页面但 buffer pool 满了
3. **InnoDB Monitor**：后台线程定期扫描（约1秒间隔）
4. **Shutdown**：优雅关闭时刷全部脏页

**WAL 性能提升原理**：
```
传统方式（随机写）: 磁盘 seek ~10ms/次 → 100 IOPS
WAL方式（顺序写）: 磁盘顺序写 ~200MB/s → 百万 IOPS

关键：redo log 是顺序追加写，而数据页是随机写。
把随机写变成顺序写，性能提升100x+
```

</details>

<details>
<summary>Q2: Redo Log 的环形缓冲区写满后怎么处理？checkpoint 的作用是什么？</summary>

**答案**：

**流程**：
```
write_pos →→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→
            |                          |
           旧数据                    新写入
           
1. write_pos 到达 RedoLogSize 末尾 → 回绕到 0
2. 但不能覆盖 checkpoint 位置的数据
3. checkpoint 推进：刷脏页到磁盘 → 更新 checkpoint_lsn
4. 如果 write_pos 追上 checkpoint → 阻塞等待
```

**checkpoint 作用**：标记"这个LSN之前的redo记录可以安全删除"。没有checkpoint，redo log会无限增长。

</details>

<details>
<summary>Q3: Buffer Pool 的 LRU 改进版（Young-Free List）解决了什么问题？</summary>

**答案**：

**经典 LRU 问题**：全表扫描会污染 LRU 列表——大量新页被放到头部，真正热数据被挤到尾部。

**InnoDB 改进**：
```
LRU List 分成三部分：
┌─────────────────────────────────────────────┐
│  Young List    │  Free List  │  Old List    │
│  (最近访问)     │  (新页面)    │  (老页面)     │
│                                              │
│  插入位置: Young 头部                        │
│  旧→新转换: Old → Young → Free → 淘汰       │
└─────────────────────────────────────────────┘

关键：新页面先放 Free List，访问后才进 Young，
再访问才进入 Old。Old 中的页面才可能被淘汰。
全表扫描的页面在 Old 之前就淘汰了。
```

</details>
