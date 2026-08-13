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
   ├── 每个进程维护一个 vruntime
   ├── 调度器选择 vruntime 最小的进程执行
   └── 保证所有进程获得公平的 CPU 时间

2. 调度器实体 (sched_entity)
   ├── 红黑树节点
   ├── 权重 (nice 值)
   └── 虚拟运行时间

3. 调度器类 (sched_class)
   ├── RT 调度类 (实时)
   ├── CFS 调度类 (普通)
   └── IDLE 调度类 (空闲)
```

### 1.2 Go 实现调度模拟

```go
// scheduler.go

package scheduler

import (
    "container/heap"
    "time"
)

type Process struct {
    ID          int
    BurstTime   int
    Remaining   int
    VRuntime    float64
    Priority    int
}

type ProcessHeap []*Process

func (h ProcessHeap) Len() int { return len(h) }
func (h ProcessHeap) Less(i, j int) bool {
    return h[i].VRuntime < h[j].VRuntime
}
func (h ProcessHeap) Swap(i, j int) { h[i], h[j] = h[j], h[i] }

func (h *ProcessHeap) Push(x interface{}) {
    *h = append(*h, x.(*Process))
}

func (h *ProcessHeap) Pop() interface{} {
    old := *h
    n := len(old)
    x := old[n-1]
    *h = old[:n-1]
    return x
}

func (h *ProcessHeap) Push(x interface{}) {
    *h = append(*h, x.(*Process))
}

func (h *ProcessHeap) Pop() interface{} {
    old := *h
    n := len(old)
    x := old[n-1]
    *h = old[:n-1]
    return x
}

func (s *Scheduler) Next() *Process {
    if h.Len() == 0 {
        return nil
    }
    return heap.Pop(h).(*Process)
}
```

---

## 2. 内存管理

### 2.1 虚拟内存

```
虚拟内存管理：

┌─────────────────────────────────────────────────────────────┐
│                  虚拟地址空间                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户空间                                                   │
│  ├── 代码段 (.text)                                         │
│  ├── 数据段 (.data)                                         │
│  ├── 堆 (heap)                                              │
│  └── 栈 (stack)                                             │
│                                                             │
│  内核空间                                                   │
│  ├── 内核代码                                               │
│  ├── 内核数据                                               │
│  └── 页表                                                   │
│                                                             │
│  TLB (Translation Lookaside Buffer)                         │
│  └── 缓存虚拟地址到物理地址的映射                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 页表结构

```
多级页表：

x86_64 四级页表：
PML4 → PDPT → PD → PT → Physical Page

┌─────────────────────────────────────────────────────────────┐
│                    页表结构                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PML4 (Page Map Level 4)                                    │
│  └── PDPT (Page Directory Pointer Table)                   │
│      └── PD (Page Directory)                               │
│          └── PT (Page Table)                                │
│              └── Page Frame (4KB)                           │
│                                                             │
│  地址分解 (48位有效地址):                                     │
│  ┌──────┬──────┬──────┬──────┬───────────┐                │
│  │ PML4 │ PDPT │  PD  │  PT  │   Offset  │                │
│  │ 9bit │ 9bit │ 9bit │ 9bit │   12bit   │                │
│  └──────┴──────┴──────┴──────┴───────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 网络栈

### 3.1 TCP 协议栈

```
TCP 协议栈层次：

应用层
  ├── HTTP
  ├── HTTPS
  ├── FTP
  └── SMTP

传输层 (TCP/UDP)
  ├── TCP: 面向连接、可靠传输
  └── UDP: 无连接、不可靠

网络层 (IP)
  ├── IPv4
  └── IPv6

网络接口层
  ├── Ethernet
  ├── WiFi
  └── VPN
```

### 3.2 TCP 状态机

```
TCP 状态转换：

CLOSED → LISTEN → SYN_SENT → SYN_RECEIVED → ESTABLISHED
                                    ↓              ↓
                              FIN_WAIT_1 ←→ CLOSE_WAIT
                                    ↓              ↓
                              FIN_WAIT_2 ←→ CLOSING
                                    ↓              ↓
                                TIME_WAIT → CLOSE
```

### 3.3 Go 实现 TCP Server

```go
// tcp_server.go

package main

import (
    "net"
    "fmt"
)

func main() {
    listener, err := net.Listen("tcp", ":8080")
    if err != nil {
        panic(err)
    }
    defer listener.Close()
    
    for {
        conn, err := listener.Accept()
        if err != nil {
            continue
        }
        go handleConnection(conn)
    }
}

func handleConnection(conn net.Conn) {
    defer conn.Close()
    
    buf := make([]byte, 4096)
    for {
        n, err := conn.Read(buf)
        if err != nil {
            return
        }
        conn.Write(buf[:n])
    }
}
```

---

## 4. 文件系统

### 4.1 VFS 架构

```
虚拟文件系统 (VFS) 架构：

┌─────────────────────────────────────────────────────────────┐
│                    VFS 架构                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  系统调用接口                                                │
│  ├── open(), close(), read(), write()                      │
│  └── ioctl(), mmap()                                       │
│                                                             │
│  VFS 层                                                      │
│  ├── 文件描述符表                                            │
│  ├── inode 缓存                                              │
│  └── dentry 缓存                                            │
│                                                             │
│  文件系统实现                                                │
│  ├── ext4                                                   │
│  ├── xfs                                                    │
│  ├── btrfs                                                  │
│  └── tmpfs                                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 inode 结构

```
inode 关键信息：

┌─────────────────────────────────────────────────────────────┐
│                      inode 结构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  文件属性                                                    │
│  ├── 文件类型 (regular, directory, symlink)                 │
│  ├── 权限 (rwxrwxrwx)                                       │
│  ├── 所有者/组                                               │
│  ├── 大小                                                    │
│  ├── 时间戳 (mtime, ctime, atime)                           │
│  └── 链接数                                                  │
│                                                             │
│  数据块指针                                                  │
│  ├── 直接块指针 (12个)                                      │
│  ├── 间接块指针 (1个)                                       │
│  ├── 双重间接块指针 (1个)                                    │
│  └── 三重间接块指针 (1个)                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 生产优化

### 5.1 内核参数调优

```bash
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535

# 文件描述符
fs.file-max = 1000000
fs.nr_open = 1000000

# 内存优化
vm.swappiness = 10
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5

# 调度优化
kernel.sched_migration_cost_ns = 5000000
```

### 5.2 性能监控

```bash
# CPU 监控
top
mpstat -P ALL 1

# 内存监控
free -h
vmstat 1

# 磁盘监控
iostat -x 1
df -h

# 网络监控
netstat -s
ss -s
iftop

# 系统调用追踪
strace -p <pid>
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| CPU 高负载 | 响应慢 | `top`, `vmstat` | 定位热点进程 |
| 内存泄漏 | 内存持续增长 | `free`, `vmstat` | 检查进程内存 |
| 磁盘满 | 写入失败 | `df`, `du` | 清理过期数据 |
| 网络拥塞 | 延迟高 | `netstat`, `iftop` | 调整内核参数 |
| 进程僵死 | 无法结束 | `ps`, `kill -9` | 强制终止 |

### 6.2 调试工具

```bash
# 查看进程信息
ps aux | grep <process>

# 查看线程
ps -T -p <pid>

# 查看文件描述符
ls -l /proc/<pid>/fd

# 查看内存映射
cat /proc/<pid>/maps

# 查看系统调用
strace -f -p <pid>

# 查看性能事件
perf top
perf stat
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 调度 | CFS 完全公平调度 |
| 内存 | 虚拟内存 + 页表 |
| 网络 | TCP/IP 协议栈 |
| 文件 | VFS + inode |

### 7.2 最佳实践

- [ ] 合理调优内核参数
- [ ] 监控系统关键指标
- [ ] 定期清理资源
- [ ] 建立故障应急预案
- [ ] 性能测试验证

---

*最后更新：2026-08-11*
*作者：Ryan*
