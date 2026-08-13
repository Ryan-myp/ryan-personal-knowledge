# Go Channel 实现原理 - 资深专家深度实现

## 一、Channel 数据结构

```go
// src/runtime/chan.go

type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形队列大小
    buf      unsafe.Pointer // 环形队列缓冲区
    elemsize uint16
    closed   uint32         // 是否关闭
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的goroutine队列
    sendq    waitq          // 等待发送的goroutine队列
    lock     mutex
    // 用于统计
    recv_cnt int64
    send_cnt int64
}

// waitq 等待队列
type waitq struct {
    first *sudog
    last  *sudog
}

// sudog goroutine等待节点
type sudog struct {
    g       *G
    elem    unsafe.Pointer // 数据元素
    next    *sudog
    prev    *sudog
    lock    mutex
    // 用于select
    selectdone *uint32 // 等待唤醒
    // 队列链接
    waitlink *sudog // g.waitq.next 或 seletq.waitc
    waitside bool   // 是否在等待侧
}
```

## 二、Channel 操作原理

### 2.1 发送操作 chansend

```go
func chansend(c *hchan, ep unsafe.Pointer, block bool, sender unsafe.Pointer) bool {
    // 快速路径：缓冲区有空间
    if c.qcount < c.dataqsiz {
        // 计算写入位置
        qp := chanbuf(c, c.sendx)
        // 直接拷贝数据
        typedmemmove(c.elemtype, qp, ep)
        c.sendx++
        if c.sendx == c.dataqsiz {
            c.sendx = 0
        }
        c.qcount++
        // 唤醒等待接收的goroutine
        wakeq(c.recvq, c.elemtype)
        return true
    }
    
    // 慢路径：阻塞等待
    if !block {
        return false
    }
    
    // 获取当前goroutine
    gp := getg()
    mysg := acquireSudog()
    mysg.releasetime = schednow
    mysg.g = gp
    mysg.elem = ep
    mysg.waitlink = nil
    
    // 加入发送队列
    lock(&c.lock)
    if c.closed != 0 {
        unlock(&c.lock)
        panic(plainError("send on closed channel"))
    }
    
    // 尝试从接收者直接传递
    if sg := c.recvq.dequeue(); sg != nil {
        // 直接传递给接收者
        copyToChan(mysg, sg)
        releasemysg(mysg)
        return true
    }
    
    // 加入等待队列
    c.sendq.enqueue(mysg)
    goready(mysg.g, false)
    stopm()
    schedule()
    
    // 唤醒后检查
    lock(&c.lock)
    if sg := c.recvq.dequeue(); sg != nil {
        copyToChan(mysg, sg)
        releasemysg(mysg)
        return true
    }
    unlock(&c.lock)
    
    return false
}

// copyToChan 直接数据传递
func copyToChan(mysg, sg *sudog) {
    if mysg.elem != nil {
        typedmemmove(sg.elem, mysg.elem)
        sg.elem = nil
    }
    if sg.elem != nil {
        typedmemmove(mysg.elem, sg.elem)
        mysg.elem = nil
    }
}
```

### 2.2 接收操作 chanrecv

```go
func chanrecv(c *hchan, ep unsafe.Pointer, block bool) (selected bool, received bool) {
    // 快速路径：缓冲区有数据
    if c.qcount > 0 {
        // 计算读取位置
        qp := chanbuf(c, c.recvx)
        if ep != nil {
            typedmemmove(c.elemtype, ep, qp)
        }
        typedmemclr(c.elemtype, qp)
        c.recvx++
        if c.recvx == c.dataqsiz {
            c.recvx = 0
        }
        c.qcount--
        // 唤醒等待发送的goroutine
        wakeq(c.sendq, c.elemtype)
        return true, true
    }
    
    // Channel已关闭且无数据
    if c.closed == 0 {
        // 阻塞等待
        if !block {
            return false, false
        }
        // ... 等待逻辑 ...
    }
    
    // Channel已关闭
    if ep != nil {
        typedmemclr(c.elemtype, ep)
    }
    return true, true
}
```

## 三、Channel 关闭

```go
// closechan 关闭Channel
func closechan(c *hchan) {
    if c == nil {
        panic(plainError("send on nil channel"))
    }
    
    lock(&c.lock)
    if c.closed != 0 {
        unlock(&c.lock)
        panic(plainError("close of closed channel"))
    }
    
    c.closed = 1
    
    // 唤醒所有等待的发送者
    var glist gList
    for {
        sg := c.sendq.dequeue()
        if sg == nil {
            break
        }
        if sg.elem != nil {
            typedmemclr(c.elemtype, sg.elem)
            sg.elem = nil
        }
        glist.push(sg.g)
    }
    
    // 唤醒所有等待的接收者
    for {
        sg := c.recvq.dequeue()
        if sg == nil {
            break
        }
        glist.push(sg.g)
    }
    
    unlock(&c.lock)
    
    // 批量唤醒
    for !glist.empty() {
        gp := glist.pop()
        gp.schedlink = 0
        ready(gp, 0, 0)
    }
}
```

## 四、无缓冲 vs 有缓冲

```go
package channel

// 无缓冲Channel: 同步通信
func syncChannel() {
    ch := make(chan int) // 容量为0
    
    go func() {
        ch <- 1 // 阻塞直到接收者就绪
    }()
    
    <-ch // 阻塞直到发送者完成
}

// 有缓冲Channel: 异步通信
func asyncChannel() {
    ch := make(chan int, 10) // 容量为10
    
    ch <- 1 // 只要buffer不满就不会阻塞
    ch <- 2
    // ...
}

// Channel 容量选择
// • 无缓冲: 严格同步，确保上下游协调
// • 有缓冲: 解耦速度，适合批量处理
```

## 五、面试高频题

### Q1: 无缓冲和有缓冲Channel有什么区别？

```
A:
• 无缓冲Channel:
  - 发送和接收必须同时就绪
  - 实现严格的同步通信
  - 不会产生数据积压
  
• 有缓冲Channel:
  - 发送在buffer未满时不阻塞
  - 实现异步通信
  - 可以缓冲数据，解耦生产消费速度

典型场景:
• 无缓冲: RPC调用、需要确认的操作
• 有缓冲: 批量处理、限流、消息队列
```

### Q2: Channel 关闭后的行为？

```
A:
• 关闭后可以继续读取，会返回零值和ok=false
• 向关闭的Channel发送会panic
• 关闭多次会panic
• (nil Channel)发送/接收会永久阻塞
```

### Q3: 如何实现一个超时控制的Channel？

```go
func withTimeout(ch chan int, timeout time.Duration) (int, error) {
    select {
    case v := <-ch:
        return v, nil
    case <-time.After(timeout):
        return 0, context.DeadlineExceeded
    }
}
```

## 六、自测题

1. Channel的底层数据结构是什么？
2. 如何实现一个安全的Channel Pool？
3. 解释Channel的send/recv操作在什么情况下会阻塞？

---

## 参考文档

- [Go Channel源码](https://github.com/golang/go/blob/master/src/runtime/chan.go)
- [Understanding Go Channels](https://go.dev/blog/pipelines)
