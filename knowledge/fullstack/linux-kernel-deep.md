# Linux 内核深度：进程调度/内存管理/网络栈

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 Linux 内核

```
Linux 内核 = 操作系统的心脏

核心组件：
1. 进程调度器：决定谁用 CPU
2. 内存管理器：决定谁用多少内存
3. 文件系统：决定数据怎么存
4. 网络栈：决定数据怎么传输
5. 设备驱动：决定怎么和硬件交互
```

### Linux 内核核心概念

```
1. 进程 vs 线程：进程是资源分配单位，线程是调度单位
2. 虚拟内存：每个进程有独立的地址空间
3. 页表：虚拟地址到物理地址的映射
4. 中断：硬件或软件信号
5. 系统调用：用户态到内核态的桥梁
```

---

## 第二部分：进程调度

### 2.1 CFS 调度器

```
CFS（Completely Fair Scheduler）：

核心思想：
- 每个进程都应该得到公平的 CPU 时间
- 使用红黑树管理进程
- 按虚拟运行时间排序

关键概念：
-vruntime：虚拟运行时间
-weight：进程权重（nice 值）
-load：进程负载
```

### 2.2 Go 实现简易调度器

```go
package scheduler

import (
    "container/heap"
    "context"
    "sync"
    "time"
)

// Process 进程
type Process struct {
    ID         int
    Priority   int       // 0-19, 越小优先级越高
    BurstTime  time.Duration
    RemainTime time.Duration
    ArrivalTime time.Time
    VRuntime   time.Duration // 虚拟运行时间
}

// Scheduler 调度器
type Scheduler struct {
    processes []*Process
    running   *Process
    mu        sync.Mutex
    ctx       context.Context
    cancel    context.CancelFunc
}

func NewScheduler() *Scheduler {
    ctx, cancel := context.WithCancel(context.Background())
    return &Scheduler{
        ctx: ctx,
        cancel: cancel,
    }
}

// AddProcess 添加进程
func (s *Scheduler) AddProcess(p *Process) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    s.processes = append(s.processes, p)
    heap.Fix(&s.processHeap, p.ID)
}

// Schedule 调度
func (s *Scheduler) Schedule() *Process {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    if len(s.processes) == 0 {
        return nil
    }
    
    // 选择 vruntime 最小的进程
    minVRuntime := s.processes[0]
    for _, p := range s.processes {
        if p.VRuntime < minVRuntime.VRuntime {
            minVRuntime = p
        }
    }
    
    // 从队列中移除
    for i, p := range s.processes {
        if p.ID == minVRuntime.ID {
            s.processes = append(s.processes[:i], s.processes[i+1:]...)
            break
        }
    }
    
    s.running = minVRuntime
    return minVRuntime
}

// Tick 时钟滴答
func (s *Scheduler) Tick() {
    if s.running == nil {
        return
    }
    
    s.running.VRuntime += time.Millisecond
    s.running.RemainTime -= time.Millisecond
    
    if s.running.RemainTime <= 0 {
        // 进程完成，放回队列
        s.processes = append(s.processes, s.running)
        s.running = nil
    }
}
```

---

## 第三部分：内存管理

### 3.1 虚拟内存

```
虚拟内存层次：
L1 Cache (~1ns) → L2 Cache (~3ns) → L3 Cache (~15ns)
→ 物理内存 (~100ns) → Swap (~10ms)

页表结构：
4KB 页面 = 2^12
x86-64 四级页表：
PGD → PUD → PMD → PTE → Physical Address

TLB（Translation Lookaside Buffer）：
缓存页表转换，避免每次访问都查页表
```

### 3.2 Go 实现内存分配器

```go
package memory

import (
    "sync"
    "unsafe"
)

// Allocator 内存分配器
type Allocator struct {
    pools     [32]*Pool  // 32 个大小类别
    mu        sync.Mutex
}

type Pool struct {
    size     uintptr
    objects  chan []byte
    capacity int
}

func NewAllocator() *Allocator {
    a := &Allocator{}
    
    // 创建不同大小的池
    sizes := []uintptr{16, 32, 64, 128, 256, 512, 1024, 2048, 4096}
    for _, size := range sizes {
        a.pools[sizeIndex(size)] = &Pool{
            size:     size,
            objects:  make(chan []byte, 100),
            capacity: 100,
        }
    }
    
    return a
}

func (a *Allocator) Alloc(size uintptr) unsafe.Pointer {
    idx := sizeIndex(size)
    
    // 从小对象池中分配
    if pool := a.pools[idx]; pool != nil {
        select {
        case obj := <-pool.objects:
            return unsafe.Pointer(&obj[0])
        default:
            // 池空了，分配新对象
            obj := make([]byte, pool.size)
            return unsafe.Pointer(&obj[0])
        }
    }
    
    // 大对象直接分配
    obj := make([]byte, size)
    return unsafe.Pointer(&obj[0])
}

func (a *Allocator) Free(ptr unsafe.Pointer, size uintptr) {
    idx := sizeIndex(size)
    if pool := a.pools[idx]; pool != nil {
        select {
        case pool.objects <- *(*[]byte)(ptr):
        default:
            // 池满了，丢弃
        }
    }
}

func sizeIndex(size uintptr) int {
    if size <= 16 {
        return 0
    }
    idx := 0
    for size > 16<<(idx+4) {
        idx++
    }
    return idx
}
```

---

## 第四部分：网络栈

### 4.1 Linux 网络栈

```
应用层 → socket() → sendto()
  ↓
传输层 → TCP/UDP 处理
  ↓
网络层 → IP 路由 → 选择网卡
  ↓
链路层 → Ethernet 封装 → 发送
```

### 4.2 Go 实现网络协议栈

```go
package network

import (
    "context"
    "encoding/binary"
    "net"
)

// ProtocolStack 协议栈
type ProtocolStack struct {
    transport *TransportLayer
    network   *NetworkLayer
    link      *LinkLayer
}

// TransportLayer 传输层
type TransportLayer struct {
    tcp  *TCPConnection
    udp  *UDPConnection
}

// NetworkLayer 网络层
type NetworkLayer struct {
    routes []Route
}

type Route struct {
    Destination string
    Gateway     string
    Interface   string
}

// LinkLayer 链路层
type LinkLayer struct {
    interfaces map[string]*Interface
}

type Interface struct {
    Name    string
    MAC     net.HardwareAddr
    MTU     int
}

// Send 发送数据包
func (ps *ProtocolStack) Send(ctx context.Context, data []byte, dstIP string) error {
    // 1. 查找路由
    route := ps.network.FindRoute(dstIP)
    if route == nil {
        return fmt.Errorf("no route to host")
    }
    
    // 2. 封装 IP 包
    ipPacket := ps.network.Encapsulate(data, route.Destination)
    
    // 3. 封装以太网帧
    ethFrame := ps.link.Encapsulate(ipPacket, route.Interface)
    
    // 4. 发送
    return ps.link.Send(ethFrame)
}
```

---

## 第五部分：生产排障案例

### 5.1 CPU 飙高

```
现象：服务器 CPU 使用率 100%

排查：
1. top -H -p <pid> 查看线程
2. strace -p <pid> 跟踪系统调用
3. perf record 性能分析

根因：goroutine 泄漏导致 CPU 高

解决方案：
1. 使用 pprof 分析
2. 修复 goroutine 泄漏
3. 添加监控告警
```

### 5.2 内存泄漏

```
现象：服务器内存持续增长

排查：
1. free -m 查看内存使用
2. pprof heap 查看堆内存
3. dmesg 查看 OOM

根因：大对象未及时释放

解决方案：
1. 使用 pprof 定位
2. 优化内存分配
3. 添加 GC 调优
```

---

## 第六部分：自测题

### 问题 1
CFS 调度器的工作原理？

<details>
<summary>查看答案</summary>

1. **虚拟运行时间**：vruntime
2. **红黑树**：按 vruntime 排序
3. **公平性**：每个进程得到公平 CPU 时间
4. **权重**：nice 值影响权重
5. **Go 实现**：Scheduler

</details>

### 问题 2
虚拟内存的优势？

<details>
<summary>查看答案</summary>

1. **隔离**：每个进程独立地址空间
2. **共享**：代码段可以共享
3. **交换**：内存不足时 swap
4. **保护**：内存访问保护
5. **Go 实现**：Allocator

</details>

### 问题 3
Linux 网络栈的工作流程？

<details>
<summary>查看答案</summary>

1. **Socket API**：应用层接口
2. **传输层**：TCP/UDP
3. **网络层**：IP 路由
4. **链路层**：Ethernet
5. **Go 实现**：ProtocolStack

</details>

---

*本文档基于 Linux 内核原理整理。*