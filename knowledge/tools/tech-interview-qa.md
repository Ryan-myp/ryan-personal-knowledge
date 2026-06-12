# 技术面试 Q&A

> Go 语言 / 系统设计 / 数据库 / 网络 — 面试高频题

---

## Go 语言

### GMP 调度模型
- G: goroutine（用户态线程）
- M: OS thread
- P: processor（调度器核心）
- M:N 模型：G → M（线程池）→ P（OS 线程）
- GOMAXPROCS = CPU 核数

### GC 调优
- 三色标记 + 写屏障
- GOGC=100 默认，可调优
- Go 1.12+ 三色标记 + 混合写屏障
- Go 1.17+ 后台 GC 线程

### 常见面试题
1. interface 底层结构
2. map 扩容机制
3. channel 实现原理
4. sync.Pool 使用场景

---

## 系统设计

### 分布式 ID
- Snowflake：41bit 时间 + 10bit 机器 + 12bit 序列
- 淘宝 Leaf：号段模式
- 美团 Leaf：ZooKeeper

### CAP 选择
- CP：分布式锁、预算扣减
- AP：竞价、曝光日志

---

## Go 代码示例

### GMP 调度器示例

```go
package main

import (
    "fmt"
    "runtime"
    "sync"
)

func main() {
    // 设置 GOMAXPROCS
    runtime.GOMAXPROCS(runtime.NumCPU())
    
    var wg sync.WaitGroup
    ch := make(chan int, 100)
    
    // 启动 worker goroutines
    for i := 0; i < 10; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            for n := range ch {
                fmt.Printf("Worker %d: %d\n", id, n)
            }
        }(i)
    }
    
    // 发送任务
    for i := 0; i < 100; i++ {
        ch <- i
    }
    close(ch)
    wg.Wait()
}
```

### map 扩容演示

```go
package main

import "fmt"

func main() {
    m := make(map[string]int)
    
    // 小 map：底层是 smallMap 结构（hmap + 小数组）
    // 大 map：底层是 hmap + bmap 链表
    
    for i := 0; i < 100; i++ {
        m[fmt.Sprintf("key%d", i)] = i
    }
    
    fmt.Println(len(m)) // 100
    
    // 扩容触发条件：
    // 1. 负载因子 > 6.5
    // 2. 找太多 overflow bucket
}
```

---

## 自测题

### 问题 1
Go 的 interface 底层结构是什么？

<details>
<summary>查看答案</summary>

1. **iface 结构**：
```go
type iface struct {
    tab  *itab  // 类型信息
    data unsafe.Pointer  // 数据指针
}

type itab struct {
    inter  *interfacetype  // 接口类型
    _type  *type           // 具体类型
    hash   uint32          // _type 的 hash
    _      [4]byte
    fun    [1]uintptr      // 方法实现数组
}
```
2. **空 interface**（interface{}）：无需存储方法指针
3. **具体类型实现接口**：编译器自动生成 itab

</details>

### 问题 2
channel 的实现原理是什么？

<details>
<summary>查看答案</summary>

1. **hchan 结构**：
```go
type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形队列大小
    buf      unsafe.Pointer // 环形队列缓冲区
    elemsize uint16         // 元素大小
    closed   uint32         // 是否关闭
    elemtype *tyoe          // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 goroutine 队列
    sendq    waitq          // 等待发送的 goroutine 队列
    lock     mutex          // 互斥锁
}
```
2. **无缓冲 channel**：发送和接收必须同时就绪
3. **有缓冲 channel**：缓冲未满时发送直接成功
4. **close + range**：关闭后仍可读取剩余元素

</details>

### 问题 3
广告平台中 Snowflake ID 的机器 ID 如何分配？

<details>
<summary>查看答案</summary>

1. **中心化分配**：Etcd/ZooKeeper 全局分配
2. **分段分配**：每台机器分配一段 ID，用完再申请
3. **Go 实现**：
```go
type Snowflake struct {
    machineID     int64
    sequence      int64
    lastTimestamp int64
}

func (sf *Snowflake) NextID() int64 {
    timestamp := time.Now().UnixMilli()
    
    if timestamp == sf.lastTimestamp {
        sf.sequence++
        if sf.sequence > 4095 {
            for timestamp <= sf.lastTimestamp {
                timestamp = time.Now().UnixMilli()
            }
            sf.sequence = 0
        }
    } else {
        sf.sequence = 0
    }
    
    sf.lastTimestamp = timestamp
    id := (timestamp << 22) | (sf.machineID << 12) | sf.sequence
    return id
}
```
4. **广告平台**：不同服务使用不同机器 ID，避免冲突

</details>

---

*本文档基于面试高频题整理。*