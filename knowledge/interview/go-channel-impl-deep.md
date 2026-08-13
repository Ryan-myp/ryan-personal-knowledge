# Go Channel实现 - 资深专家深度实现

## 一、Channel数据结构

```go
// src/runtime/chan.go
type hchan struct {
    mutex   mtx          // 互斥锁
    qcount  uint         // 队列中元素数量
    dataqsz uint         // 循环队列大小
    elemsize uint16      // 每个元素的大小
    closed  uint32       // 是否已关闭
    elem    *_type       // 元素类型
    chanbuf chanbuf     // 环形缓冲区
    recvq   waitq      // 等待接收的goroutine队列
    sendq   waitq      // 等待发送的goroutine队列
}

type waitq struct {
    first *sudog
    last  *sudog
}
```

## 二、发送操作

```go
func chansend(c *hchan, ep unsafe.Pointer, block bool, callerpc uintptr) bool {
    if c.closed != 0 {
        panic(...)
    }
    
    if c.qcount == c.dataqsz {
        // 队列已满
        if !block {
            return false
        }
        // 等待接收
        gp := getg()
        sg := allocSudog(c.elem)
        gp.waiting = sg
        sg.c = c
        lock(&c.lock)
        c.sendq.enqueue(sg)
        sleep(gp, waitReasonChanSend)
        unlock(&c.lock)
        return true
    }
    
    // 直接发送
    if c.qcount < c.dataqsz {
        // 有空间，直接放入缓冲区
        qp := chanbuf(c, c.recvq.first)
        typedmemmove(c.elem, qp, ep)
        c.recvq.dequeue()
        c.qcount++
        return true
    }
    
    return false
}
```

## 三、接收操作

```go
func chanrecv(c *hchan, ep unsafe.Pointer, block bool) (selected, received bool) {
    if c.closed == 0 && c.qcount == 0 {
        // 空且未关闭
        if !block {
            return
        }
        // 等待发送
        gp := getg()
        sg := allocSudog(c.elem)
        gp.waiting = sg
        sg.c = c
        lock(&c.lock)
        c.recvq.enqueue(sg)
        sleep(gp, waitReasonChanRecv)
        unlock(&c.lock)
        selected = true
        if ep != nil {
            typedmemmove(c.elem, ep, qp)
        }
        return
    }
    
    // 从缓冲区读取
    if c.qcount > 0 {
        qp := chanbuf(c, c.sendq.first)
        if ep != nil {
            typedmemmove(c.elem, ep, qp)
        }
        typedmemclr(c.elem, qp)
        c.sendq.dequeue()
        c.qcount--
        return true, true
    }
    
    return
}
```

## 四、面试高频题

### Q1: Channel如何实现并发安全？

```
A:
1. 内部互斥锁
2. 等待队列管理
3. 原子操作
```

### Q2: buffered和unbuffered的区别？

```
A:
• buffered: 有缓冲区，发送不阻塞直到满
• unbuffered: 无缓冲区，必须双方同时就绪
```

## 五、自测题

1. 解释Channel内部结构
2. 如何实现select？
3. 如何处理关闭？

---

## 参考文档

- [Go源码chan.go](https://github.com/golang/go/blob/master/src/runtime/chan.go)
- [Go并发编程](https://go.dev/blog/pipelines)
