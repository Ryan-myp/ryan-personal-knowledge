# Linux 内核深度解析

> 深入 Linux 内核：进程调度、内存管理、网络栈、文件系统。
> 源码级分析，包含生产环境调优。
> 适用对象：系统工程师、DevOps、后端工程师

---

## 1. 进程调度

### 1.1 CFS 调度器

```
完全公平调度器 (CFS) 原理：

1. 虚拟运行时间 (vruntime)
   - 每个进程维护一个 vruntime
   - 调度器选择 vruntime 最小的进程

2. 权重计算
   - nice 值决定权重
   - nice -20: 权重 1024
   - nice 0: 权重 100
   - nice 19: 权重 10

3. 调度决策
   - 选择 vruntime 最小的进程
   - 运行一个时间片后更新 vruntime
```

### 1.2 Go 实现调度器

```go
// scheduler.go

package scheduler

import (
    "container/heap"
    "sync"
)

type Process struct {
    id       int
    vruntime int64
    priority int
    state    string
}

type ProcessQueue struct {
    processes []*Process
    mu        sync.Mutex
}

func (pq *ProcessQueue) Add(p *Process) {
    pq.mu.Lock()
    defer pq.mu.Unlock()
    pq.processes = append(pq.processes, p)
}

func (pq *ProcessQueue) Next() *Process {
    pq.mu.Lock()
    defer pq.mu.Unlock()
    
    if len(pq.processes) == 0 {
        return nil
    }
    
    // 找 vruntime 最小的
    min := pq.processes[0]
    for _, p := range pq.processes[1:] {
        if p.vruntime < min.vruntime {
            min = p
        }
    }
    
    // 移除并返回
    pq.processes = remove(pq.processes, min)
    return min
}

func remove(processes []*Process, p *Process) []*Process {
    for i, proc := range processes {
        if proc.id == p.id {
            return append(processes[:i], processes[i+1:]...)
        }
    }
    return processes
}
```

---

## 2. 内存管理

### 2.1 内存布局

```
进程内存布局：

┌─────────────────────────────────────────────────────────────┐
│                    用户空间                                  │
├─────────────────────────────────────────────────────────────┤
│  Stack (栈)                                                 │
│  ├── 函数调用信息                                            │
│  ├── 局部变量                                                │
│  └── 向下增长                                                │
├─────────────────────────────────────────────────────────────┤
│  Heap (堆)                                                  │
│  ├── malloc/new 分配                                         │
│  └── 向上增长                                                │
├─────────────────────────────────────────────────────────────┤
│  Data (数据段)                                              │
│  ├── 全局变量                                                │
│  └── 静态变量                                                │
├─────────────────────────────────────────────────────────────┤
│  Text (代码段)                                              │
│  └── 可执行代码                                              │
├─────────────────────────────────────────────────────────────┤
│                    内核空间                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 虚拟内存

```go
// virtual_memory.go

package memory

type VirtualMemory struct {
    pages       map[uintptr]*Page
    pageTable   *PageTable
}

type Page struct {
    address  uintptr
    physical uintptr
    refCount int
    dirty    bool
}

type PageTable struct {
    entries [4096]*Page
}

func (vm *VirtualMemory) Map(vaddr, paddr uintptr, size uintptr) error {
    // 页表映射
    for offset := uintptr(0); offset < size; offset += 4096 {
        page := &Page{
            address:  vaddr + offset,
            physical: paddr + offset,
            refCount: 1,
        }
        vm.pages[page.address] = page
    }
    return nil
}
```

---

## 3. 网络栈

### 3.1 TCP 协议栈

```
TCP 状态机：

CLOSED ────► SYN_SENT ────► ESTABLISHED ────► CLOSE_WAIT
   ▲                                         │
   │                                         ▼
   └──── FIN_WAIT ────► LAST_ACK ────► CLOSED
```

### 3.2 Go 实现 TCP 服务器

```go
// tcp_server.go

package network

import (
    "net"
    "sync"
)

type TCPServer struct {
    listener    net.Listener
    connections sync.Map
}

func NewTCPServer(addr string) (*TCPServer, error) {
    listener, err := net.Listen("tcp", addr)
    if err != nil {
        return nil, err
    }
    return &TCPServer{listener: listener}, nil
}

func (s *TCPServer) Start() {
    for {
        conn, err := s.listener.Accept()
        if err != nil {
            continue
        }
        s.connections.Store(conn.RemoteAddr().String(), conn)
        go s.handle(conn)
    }
}

func (s *TCPServer) handle(conn net.Conn) {
    defer conn.Close()
    buf := make([]byte, 4096)
    for {
        n, err := conn.Read(buf)
        if err != nil {
            return
        }
        // 处理请求
    }
}
```

---

## 4. 文件系统

### 4.1 VFS 层

```
虚拟文件系统 (VFS) 架构：

┌─────────────────────────────────────────────────────────────┐
│                     系统调用层                               │
│  open(), read(), write(), close()                           │
├─────────────────────────────────────────────────────────────┤
│                     VFS 层                                  │
│  ├── dentry (目录项缓存)                                    │
│  ├── inode (文件元数据)                                     │
│  └── file (打开的文件描述符)                                │
├─────────────────────────────────────────────────────────────┤
│                     文件系统层                              │
│  ├── ext4                                                   │
│  ├── xfs                                                    │
│  └── btrfs                                                  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 文件缓存

```
页缓存 (Page Cache)：

- 内核使用空闲内存缓存文件数据
- 减少磁盘 I/O
- 通过 drop_caches 清空缓存
```

---

## 5. 性能调优

### 5.1 内核参数

```bash
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65535

# 文件描述符
fs.file-max = 1000000
fs.nr_open = 1000000

# 内存优化
vm.swappiness = 10
vm.min_free_kbytes = 65536
```

### 5.2 Go 优化

```go
// optimize.go

package main

import (
    "runtime"
    "sync"
)

func main() {
    // 设置 GOMAXPROCS
    runtime.GOMAXPROCS(runtime.NumCPU())
    
    // 对象池
    var pool sync.Pool
    pool.New = func() interface{} {
        return make([]byte, 1024)
    }
    
    // 使用池
    buf := pool.Get().([]byte)
    defer pool.Put(buf)
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 调度 | CFS 公平调度 |
| 内存 | 虚拟内存 + 页表 |
| 网络 | TCP/IP 协议栈 |
| 文件 | VFS + 页缓存 |

### 6.2 最佳实践

- [ ] 合理设置内核参数
- [ ] 监控系统资源
- [ ] 优化 Go 运行时
- [ ] 使用对象池
- [ ] 调优网络栈

---

*最后更新：2026-08-11*
*作者：Ryan*
