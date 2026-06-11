
---

### MySQL InnoDB 的 Go 实现

```go
package innodb

import (
	"fmt"
	"sync"
	"time"
)

type Page struct {
	PageID   int64
	Data     []byte
	Lsn      uint64
	Type     string
	Dirty    bool
}

type BufferPool struct {
	pages     map[int64]*Page
	frameSize int
	mu        sync.RWMutex
}

func NewBufferPool(size int) *BufferPool {
	return &BufferPool{pages: make(map[int64]*Page), frameSize: size}
}

func (bp *BufferPool) Read(pageID int64) *Page {
	bp.mu.RLock()
	defer bp.mu.RUnlock()
	return bp.pages[pageID]
}

func (bp *BufferPool) Write(p *Page) {
	bp.mu.Lock()
	defer bp.mu.Unlock()
	p.Dirty = true
	bp.pages[p.PageID] = p
}

type XLock struct {
	tableID  string
	rowID    string
	granted  bool
	holder   string
	mu       sync.Mutex
}

type LockManager struct {
	locks map[string]*XLock
}

func NewLockManager() *LockManager { return &LockManager{locks: make(map[string]*XLock)} }

func (lm *LockManager) Acquire(table, row, holder string) *XLock {
	key := table + ":" + row
	lm.locks[key] = &XLock{tableID: table, rowID: row, granted: true, holder: holder}
	return lm.locks[key]
}

func main() {
	bp := NewBufferPool(1024)
	bp.Write(&Page{PageID: 1, Data: []byte("data"), Type: "DATA"})
	fmt.Printf("Page: %d, Dirty: %v\n", 1, bp.Read(1).Dirty)

	lm := NewLockManager()
	ln := lm.Acquire("users", "1", "tx_1")
	fmt.Printf("Lock: %s -> %s\n", ln.tableID, ln.holder)
}
```

---

## 自测题

### 问题 1
MySQL InnoDB 的 Buffer Pool 为什么用 LRU 链表而不是哈希表做驱逐策略？

<details>
<summary>查看答案</summary>

1. **LRU 链表**：维护最近使用顺序，O(1) 移动节点到头部
2. **哈希表**：只负责快速查找，不维护使用顺序
3. **混合结构**：实际 InnoDB 用 hash table + doubly-linked list 组合
4. **防抖动**：InnoDB 用 "young half" 和 "old half" 分区，避免扫描导致缓存污染

</details>

### 问题 2
InnoDB 的 MVCC 为什么用 undo log 而不是多版本数据页？

<details>
<summary>查看答案</summary>

1. **空间效率**：undo log 只存变更，不改动的数据页共享
2. **回滚需求**：事务回滚需要完整的历史版本
3. **快照隔离**：Read View 通过 TRX_ID 比较决定可见性
4. **redo/undo 分工**：redo 用于崩溃恢复，undo 用于 MVCC 和回滚

</details>