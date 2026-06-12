# Linux 内核核心原理

> 进程调度 / 内存管理 / 网络栈 / I/O 模型 — 广告平台高性能服务基础

---

## 第一部分：入门引导（5 分钟速览）

### 为什么广告平台需要理解 Linux 内核？

广告平台是高并发、低延迟系统：
- **实时竞价**：RTT < 100ms，需要高效的 I/O 模型
- **海量日志**：每日 TB 级日志，需要高效文件 I/O
- **高吞吐网络**：百万 QPS 网络通信
- **资源隔离**：多租户环境下避免相互干扰

理解 Linux 内核能帮助：
1. **性能调优**：理解 goroutine 调度与 OS 线程的关系
2. **问题排查**：定位 CPU steal、page fault、TCP 重传
3. **架构设计**：基于内核特性设计高性能服务

### Linux 内核架构

```
用户态（User Space）
├── Go Runtime（goroutine 调度）
├── 用户程序（HTTP 服务、Kafka Producer 等）
└── 标准 C 库（glibc/musl）

系统调用（System Call）
└── 内核态（Kernel Space）
    ├── VFS（虚拟文件系统）
    ├── 进程调度（CFS）
    ├── 内存管理（VM）
    ├── 网络栈（TCP/IP）
    ├── 块设备（Block I/O）
    └── 字符设备（驱动）
```

---

## 第二部分：进程调度

### 2.1 CFS 调度器

**CFS（Completely Fair Scheduler）** 是 Linux 默认的调度器（2.6.23+），基于 Red-Black 树实现。

### 2.2 CFS 核心概念

| 概念 | 说明 |
|------|------|
| **vruntime** | 虚拟运行时间，进程实际运行时间 / 权重 |
| **min_vruntime** | 所有进程中最小的 vruntime |
| **weight** | 进程权重，nice 值决定 |
| **priority** | 优先级 = 120 + nice（nice 范围 -20 ~ 19） |

### 2.3 CFS 调度流程

```
1. 维护一个 Red-Black 树，键值为 vruntime
2. 选择 vruntime 最小的进程执行
3. 每次 tick（1ms），更新 vruntime
4. vruntime += delta_exec * NICE_0_LOAD / weight
```

### 2.4 nice 值与调度权重

| nice 值 | 优先级 | 权重 | 说明 |
|---------|--------|------|------|
| -20 | 20 | 1333 | 最高优先级 |
| 0 | 120 | 1024 | 默认 |
| 10 | 130 | 627 | 低优先级 |
| 19 | 139 | 100 | 最低优先级 |

### 2.5 Go 中的进程/线程模型

```
Go 的 M:N 模型：
┌─────────────────────────────────┐
│           Go Runtime            │
│  goroutine pool (M:N scheduling)│
│  - P (Processor)：调度器核心     │
│  - M (Machine)：OS 线程          │
│  - G (Goroutine)：用户线程       │
└─────────────────────────────────┘
         ↓ syscall
┌─────────────────────────────────┐
│        OS Thread (M)            │
│  1:1 映射到 OS 线程              │
└─────────────────────────────────┘
         ↓ syscall
┌─────────────────────────────────┐
│         Linux CFS               │
│  调度 O(N) 个 OS 线程            │
└─────────────────────────────────┘
```

**关键理解**：
1. Go 的 P 数量 = GOMAXPROCS（默认 CPU 核数）
2. 每个 P 绑定一个或多个 M
3. M 在执行 syscall 时会被阻塞，Go Runtime 会创建新 M 继续调度 G

### 2.6 调度相关调优

```bash
# 1. 设置 CPU 亲和性（将进程绑定到特定 CPU 核）
taskset -c 0,1 ./my-service

# 2. 调整进程优先级
nice -n -10 ./my-service

# 3. 查看调度信息
ps -eo pid,nice,pri,comm | head
cat /proc/<pid>/sched

# 4. 调整 GOMAXPROCS
# Go 1.5+ 默认自动调整，无需手动设置
```

---

## 第三部分：内存管理

### 3.1 虚拟内存

Linux 使用虚拟内存，每个进程有独立的地址空间：

```
用户空间（4GB）
├── 代码段（text） — 编译后的机器码
├── 数据段（data） — 已初始化的全局变量
├── BSS 段 — 未初始化的全局变量
├── 堆（heap） — malloc/new
├── 栈（stack） — 函数调用
└── 内存映射（mmap） — 文件/匿名映射

内核空间（不显示，每个进程共享）
```

### 3.2 内存分配与 Go 的 Malloc

Go 使用自己的内存分配器（mimalloc + TCMalloc 混合）：

```
G 内存分配流程：
1. 检查 P 的 mcache（本地缓存）
2. 如果有，直接分配
3. 如果没有，从 mcentral 获取 span
4. 如果 mcentral 空，从 mheap 获取
5. 如果 mheap 空，通过 syscall 向 OS 申请

OS 层面：mmap(ANONYMOUS) → 预留虚拟地址
         madvise → 决定物理页面是否真正分配
```

### 3.3 页表与 TLB

```
虚拟地址 → TLB 查找 → 页表查找 → 物理地址

TLB（Translation Lookaside Buffer）：
- L1 TLB：48 或 64 条，1 cycle 命中
- L2 TLB：通常是 512 或 1024 条，10 cycle 命中
- 未命中：遍历页表（walk），20+ cycle

广告平台优化：
- 热点数据放在同一 NUMA 节点
- 使用 huge page（2MB）减少 TLB miss
```

### 3.4 Swap 与 OOM

```
Swap 使用场景：
- 内存充足时：避免（广告平台必须禁 swap）
- 内存紧张时：可能导致性能急剧下降

OOM Killer：
- 触发条件：内存不足 + swap 不足
- 策略：kill 占用内存最多的进程
- 广告平台：调大 vm.overcommit_memory = 1
```

### 3.5 内存优化实践

```go
// 1. 对象池复用
var bufferPool = sync.Pool{
    New: func() interface{} {
        buf := make([]byte, 32*1024)
        return &buf
    },
}

// 2. 预分配避免 GC
func makeAdResponse(adIDs []string) []byte {
    // 预分配
    buf := make([]byte, 0, len(adIDs)*100)
    for _, id := range adIDs {
        buf = append(buf, []byte(id)...)
    }
    return buf
}

// 3. 避免内存泄漏
func processAds() {
    ads := loadAds() // 大切片
    defer func() { ads = nil }()  // 帮助 GC
    result := filterAds(ads)
    return result
}
```

---

## 第四部分：网络栈

### 4.1 TCP/IP 协议栈

```
应用层（HTTP/gRPC）
   ↓
传输层（TCP/UDP） — 端口、拥塞控制
   ↓
网络层（IP） — 路由、NAT
   ↓
链路层（Ethernet/Wi-Fi） — MAC 地址
   ↓
物理层（光纤/铜缆）
```

### 4.2 Linux 网络栈关键组件

```
应用程序（read/write/sendto/recvfrom）
   ↓
Socket API
   ↓
Netfilter（iptables/nftables）
   ↓
IP 层（路由、分片、ICMP）
   ↓
传输层（TCP/UDP）
   ↓
设备驱动（eth0/wlan0）
```

### 4.3 TCP 拥塞控制

| 算法 | 说明 | 适用场景 |
|------|------|---------|
| **Reno** | 经典 AIMD | 经典算法 |
| **Cubic** | Linux 默认 | 高带宽延迟乘积网络 |
| **BBR** | Google 研发 | 数据中心、跨地域 |

### 4.4 Go 中的网络优化

```go
// 1. 设置 TCP Keepalive
server := &http.Server{
    Addr: ":8080",
    ConnContext: func(ctx context.Context, c net.Conn) context.Context {
        if tc, ok := c.(*net.TCPConn); ok {
            tc.SetKeepAlive(true)
            tc.SetKeepAlivePeriod(30 * time.Second)
            tc.SetNoDelay(true)
        }
        return ctx
    },
}

// 2. 限制连接数
limiter := rate.NewLimiter(1000, 100)
```

---

## 第五部分：I/O 模型

### 5.1 I/O 模型对比

| 模型 | 说明 | Go 中的使用 |
|------|------|-----------|
| **阻塞 I/O** | 等待 I/O 完成 | 默认 |
| **非阻塞 I/O** | 立即返回 | 可选 |
| **I/O 多路复用** | select/epoll | Go 默认使用 golang.net |
| **mmap** | 内存映射文件 | 大文件读取 |

### 5.2 epoll 机制

```
epoll 核心：
1. epoll_create() 创建 epoll 实例
2. epoll_ctl() 添加/删除/修改 fd
3. epoll_wait() 等待事件

Go 的 net 包使用 epoll（Linux）：
- Go 1.8+ 默认使用非阻塞 connect
- 通过 epoll 实现 goroutine 复用
```

### 5.3 mmap 使用

```go
// 使用 syscall.Mmap 映射文件
import "syscall"

func readMmapFile(path string) ([]byte, error) {
    fd, err := syscall.Open(path, syscall.O_RDONLY, 0)
    if err != nil {
        return nil, err
    }
    defer syscall.Close(fd)
    
    stat, _ := syscall.Fstat(fd)
    size := stat.Size
    
    data, err := syscall.Mmap(fd, 0, int(size),
        syscall.PROT_READ, syscall.MAP_SHARED)
    if err != nil {
        return nil, err
    }
    return data, nil
}
```

### 5.4 Zero-Copy

```
传统 I/O 路径：
Disk → Kernel Buffer → User Buffer → Kernel Socket Buffer → Network

Zero-Copy（sendfile）：
Disk → Kernel Buffer → Kernel Socket Buffer → Network
         ↑ 跳过用户态拷贝
         
Go 中的 Zero-Copy：
- io.Copy + syscall.Sendfile（Linux）
- 适用于文件下载、日志转发
```

---

## 第六部分：自测题

### 问题 1
Go 的 goroutine 与 Linux 线程的关系是什么？

<details>
<summary>查看答案</summary>

1. **M:N 模型**：G（goroutine）→ M（OS 线程）→ P（调度器核心）
2. **M 是线程**：Go 的 M 绑定到一个 OS 线程
3. **G 是用户态线程**：Go Runtime 调度，无需 sys...[truncated]