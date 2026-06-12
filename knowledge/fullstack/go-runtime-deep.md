# Go 进阶：内存分配器/垃圾回收/网络轮询器

> Go 内存分配 / TCMalloc 实现 / 三色标记 GC / GMP 调度器 / Netpoller 源码深度

---

## 第一部分：入门引导（5 分钟速览）

### Go 运行时三大核心

1. **内存分配器**：TCMalloc 变种，快速分配
2. **垃圾回收器**：三色标记 + 写屏障
3. **网络轮询器**：epoll/kqueue 异步 IO

### Go 内存层次结构

```
M (OS Thread) → P (Processor) → G (Goroutine)

M:0 ── P:0 ── G:1, G:2, G:3
        │
        └── M:1 ── P:1 ── G:4, G:5
```

---

## 第二部分：内存分配器

### 2.1 TCMalloc 变种实现

```go
package mimalloc

import (
    "sync"
    "unsafe"
)

// MallocState 分配器状态
type MallocState struct {
    freeLists [64][]uintptr // 64 个空闲链表，按大小分类
    mutex     sync.Mutex
    pages     map[uintptr]*Page
}

// Page 内存页
type Page struct {
    address  uintptr
    size     int
    inUse    bool
    next     *Page
}

// Allocate 分配内存
func (ms *MallocState) Allocate(size int) unsafe.Pointer {
    // 1. 确定大小类别
    class := ms.getSizeClass(size)
    
    // 2. 从空闲链表获取
    ms.mutex.Lock()
    freeList := ms.freeLists[class]
    ms.mutex.Unlock()
    
    if len(freeList) > 0 {
        // 有可用页，直接取出
        page := freeList[len(freeList)-1]
        ms.freeLists[class] = freeList[:len(freeList)-1]
        return unsafe.Pointer(page)
    }
    
    // 3. 分配新页
    return ms.allocateNewPage(class)
}

// Deallocate 释放内存
func (ms *MallocState) Deallocate(ptr unsafe.Pointer, size int) {
    class := ms.getSizeClass(size)
    
    ms.mutex.Lock()
    ms.freeLists[class] = append(ms.freeLists[class], uintptr(ptr))
    ms.mutex.Unlock()
}

func (ms *MallocState) getSizeClass(size int) int {
    // 大小类别：16, 32, 48, 64, 96, 128, 192, 256, ...
    if size <= 16 {
        return 0
    } else if size <= 32 {
        return 1
    } else if size <= 48 {
        return 2
    }
    // ... 更多类别
    return size / 16
}

func (ms *MallocState) allocateNewPage(class int) unsafe.Pointer {
    size := (class + 1) * 16
    
    // 调用系统调用分配内存
    ptr, _ := syscall.Mmap(-1, 0, size, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_ANON|syscall.MAP_PRIVATE)
    
    page := &Page{
        address: uintptr(ptr),
        size:    size,
        inUse:   true,
    }
    
    ms.pages[uintptr(ptr)] = page
    
    return unsafe.Pointer(ptr)
}
```

### 2.2 线程局部存储

```go
type ThreadLocalCache struct {
    caches map[int64]*PerThreadCache
    mu     sync.Mutex
}

type PerThreadCache struct {
    freeLists [64][]uintptr
    tid       int64
}

func (tlc *ThreadLocalCache) GetCache(tid int64) *PerThreadCache {
    tlc.mu.Lock()
    defer tlc.mu.Unlock()
    
    if cache, ok := tlc.caches[tid]; ok {
        return cache
    }
    
    cache := &PerThreadCache{tid: tid}
    tlc.caches[tid] = cache
    return cache
}
```

---

## 第三部分：垃圾回收器

### 3.1 三色标记算法

```go
type GCState struct {
    objects    map[uintptr]*Object
    white      map[uintptr]bool
    gray       []uintptr
    black      map[uintptr]bool
    writeBarriers []WriteBarrier
}

type Object struct {
    id       uintptr
    pointers []uintptr // 指向其他对象的指针
    color    string    // white, gray, black
}

type WriteBarrier struct {
    addr   uintptr
    value  uintptr
}

func (gc *GCState) StartGC() {
    // 1. 标记所有对象为白色
    for id := range gc.objects {
        gc.white[id] = true
    }
    
    // 2. 设置根对象
    roots := gc.getRoots()
    for _, root := range roots {
        gc.mark(root)
    }
    
    // 3. 执行三色标记
    gc.sweep()
}

func (gc *GCState) mark(obj *Object) {
    if obj.color == "black" {
        return
    }
    
    obj.color = "gray"
    gc.gray = append(gc.gray, obj.id)
    
    // 递归标记
    for _, ptr := range obj.pointers {
        if referenced, ok := gc.objects[ptr]; ok {
            if referenced.color == "white" {
                gc.mark(referenced)
            } else if referenced.color == "black" {
                // 写屏障：将黑色对象重新标记为灰色
                gc.writeBarrier(obj, referenced)
            }
        }
    }
    
    obj.color = "black"
    gc.black[obj.id] = true
    delete(gc.white, obj.id)
}

func (gc *GCState) sweep() {
    // 清除白色对象
    for id := range gc.white {
        delete(gc.objects, id)
    }
    
    // 重置颜色
    for id := range gc.objects {
        gc.objects[id].color = "white"
    }
    
    gc.white = make(map[uintptr]bool)
    gc.gray = nil
    gc.black = make(map[uintptr]bool)
}

func (gc *GCState) writeBarrier(from, to *Object) {
    // 写屏障：将黑色对象重新标记为灰色
    if to.color == "black" {
        to.color = "gray"
        gc.gray = append(gc.gray, to.id)
    }
}
```

### 3.2 混合写屏障

```go
type HybridWriteBarrier struct {
    dirtyBits map[uintptr]bool // 脏页位图
    mu        sync.Mutex
}

func (hw *HybridWriteBarrier) Store(addr, value uintptr) {
    // 1. 设置值
    *(*uintptr)(unsafe.Pointer(addr)) = value
    
    // 2. 标记脏页
    hw.mu.Lock()
    hw.dirtyBits[addr] = true
    hw.mu.Unlock()
}

func (hw *HybridWriteBarrier) ScanDirtyPages() []uintptr {
    hw.mu.Lock()
    defer hw.mu.Unlock()
    
    dirtyPages := make([]uintptr, 0)
    for addr, dirty := range hw.dirtyBits {
        if dirty {
            dirtyPages = append(dirtyPages, addr)
        }
    }
    
    return dirtyPages
}
```

---

## 第四部分：GMP 调度器

### 4.1 Goroutine 调度

```go
type Scheduler struct {
    gs    []*G
    np    int
    m     []*M
    p     []*P
    runq  []*G
    runqsize int
    stop  bool
}

type G struct {
    id       int64
    stack    Stack
    sp       uintptr
    pc       uintptr
    fn       unsafe.Pointer
    status   int
    sched    Context
    m        *M
}

type P struct {
    id        int
    status    int
    runq      []*G
    runnext   *G
    pd        PCache
    m         *M
    mcache    *MCache
}

type M struct {
    id       int
    g0       *G      // 系统栈 goroutine
    curg     *G      // 当前用户 goroutine
    p        P       // 绑定的 P
    nextp    P       // 下一个 P
    sched    Context
}

func (s *Scheduler) Schedule() {
    for {
        // 1. 尝试从本地运行队列获取 G
        g := s.runSafe()
        if g != nil {
            s.execute(g)
            continue
        }
        
        // 2. 从其他 P 偷工作
        g = s.stealWork()
        if g != nil {
            s.execute(g)
            continue
        }
        
        // 3. 阻塞等待
        if s.stop {
            return
        }
        
        runtime_Park()
    }
}

func (s *Scheduler) execute(g *G) {
    // 恢复 goroutine 的上下文
    g.sched.sp = g.stack.sp
    g.sched.pc = g.stack.pc
    g.m = getCurrentM()
    g.m.curg = g
    
    // 切换到 goroutine 的栈
    runtime_Gogo(&g.sched)
}
```

### 4.2 工作窃取

```go
func (s *Scheduler) stealWork() *G {
    for _, p := range s.p {
        if p == s.getCurrentP() {
            continue
        }
        
        // 从其他 P 偷一半的工作
        n := len(p.runq) / 2
        if n > 0 {
            stolen := make([]*G, n)
            copy(stolen, p.runq[:n])
            p.runq = p.runq[n:]
            
            // 添加到当前 P 的运行队列
            s.runq = append(s.runq, stolen...)
            s.runqsize += n
            
            return s.runq[0]
        }
    }
    
    return nil
}
```

---

## 第五部分：Netpoller

### 5.1 epoll 封装

```go
type Netpoller struct {
    epfd   int
    events []EpEvent
}

type EpEvent struct {
    fd    int
    events uint32
}

func (np *Netpoller) Init() error {
    // 创建 epoll 实例
    epfd, err := syscall.EpollCreate1(0)
    if err != nil {
        return err
    }
    
    np.epfd = epfd
    np.events = make([]EpEvent, 128)
    
    return nil
}

func (np *Netpoller) Register(fd int, mode int) error {
    ev := syscall.EpollEvent{
        Events: syscall.EPOLLIN,
        Fd:     int32(fd),
    }
    
    return syscall.EpollCtl(np.epfd, syscall.EPOLL_CTL_ADD, fd, &ev)
}

func (np *Netpoller) Poll(timeout int) ([]EpEvent, error) {
    n, err := syscall.EpollWait(np.epfd, np.events, timeout)
    if err != nil {
        return nil, err
    }
    
    events := make([]EpEvent, n)
    for i := 0; i < n; i++ {
        events[i] = EpEvent{
            fd:    int(np.events[i].Fd),
            events: uint32(np.events[i].Events),
        }
    }
    
    return events, nil
}
```

### 5.2 异步网络 IO

```go
type AsyncConn struct {
    conn   net.Conn
    rd     *netpoll.Registration
    wr     *netpoll.Registration
    buf    []byte
    offset int
}

func (ac *AsyncConn) Read(buf []byte) (int, error) {
    // 1. 注册读事件
    err := ac.rd.Register(syscall.EPOLLIN)
    if err != nil {
        return 0, err
    }
    
    // 2. 等待可读
    err = ac.rd.Wait()
    if err != nil {
        return 0, err
    }
    
    // 3. 读取数据
    n, err := ac.conn.Read(buf)
    if err != nil {
        return 0, err
    }
    
    return n, nil
}

func (ac *AsyncConn) Write(buf []byte) (int, error) {
    // 1. 注册写事件
    err := ac.wr.Register(syscall.EPOLLOUT)
    if err != nil {
        return 0, err
    }
    
    // 2. 等待可写
    err = ac.wr.Wait()
    if err != nil {
        return 0, err
    }
    
    // 3. 写入数据
    n, err := ac.conn.Write(buf)
    if err != nil {
        return 0, err
    }
    
    return n, nil
}
```

---

## 第六部分：自测题

### 问题 1
Go 的内存分配器为什么比 malloc/free 快？

<details>
<summary>查看答案</summary>

1. **线程局部缓存**：避免锁竞争
2. **大小类别**：预分配固定大小的块
3. **空闲链表**：快速查找可用内存
4. **批量分配**：减少系统调用次数
5. **TCMalloc 变种**：Go 的 mcache/mcentral/mspan 三级结构

</details>

### 问题 2
Go 的三色标记 GC 如何保证正确性？

<details>
<summary>查看答案</summary>

1. **写屏障**：阻止黑色对象指向白色对象
2. **混合写屏障**：平衡性能和正确性
3. **STW 阶段**：标记完成后的短暂停顿
4. **并发标记**：大部分标记工作与用户代码并发
5. **Go 实现**：使用 hybrid write barrier

</details>

### 问题 3
GMP 调度器如何避免饥饿？

<details>