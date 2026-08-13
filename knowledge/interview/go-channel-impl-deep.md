# Go Channel实现原理 - 资深专家深度实现

## 一、Channel结构

```go
// src/runtime/chan.go
type hchan struct {
    qcount   uint           // 队列中元素总数
    dataqsz  uint           // 循环队列大小
    buf      unsafe.Pointer // 元素缓冲区
    elemsize uint16
    closed   uint32
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的goroutine队列
    sendq    waitq          // 等待发送的goroutine队列
    
    lock mutex
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
        throw("chansend: close")
    }
    
    if c.qcount == c.dataqsz {
        // 队列已满
        if !block {
            return false
        }
        // 等待接收者
        gp := getg()
        mysg := acquireSudog()
        mysg.releasetime = monotime()
        mysg.g = gp
        mysg.ch = c
        mysg.elem = ep
        mysg.waitlink = nil
        gp.waiting = mysg
        c.sendq.enqueue(mysg)
        goreleasetoken = semacquire(&c.lock)
        // ... 等待唤醒
        return true
    }
    
    // 直接发送
    if c.recvq.dequeue() {
        // 有等待接收者，直接传递
        copyTo(c.recvq.dequeue(), ep)
        return true
    }
    
    // 放入缓冲区
    copyTo(c.buf, ep)
    c.sendx = (c.sendx + 1) % c.dataqsz
    c.qcount++
    return true
}
```

## 三、接收操作

```go
func chanrecv(c *hchan, ep unsafe.Pointer, block bool) (selected, ok bool) {
    if c.closed != 0 {
        // 通道关闭
        if c.qcount == 0 {
            if ep != nil {
                typedmemclr(c.elemtype, ep)
            }
            return true, false
        }
    }
    
    if c.qcount > 0 {
        // 从缓冲区接收
        if ep != nil {
            copyFrom(ep, c.recvq.dequeue())
        }
        c.recvx = (c.recvx + 1) % c.dataqsz
        c.qcount--
        return true, true
    }
    
    if !block {
        return false, false
    }
    
    // 等待发送者
    gp := getg()
    mysg := acquireSudog()
    mysg.g = gp
    mysg.ch = c
    if ep != nil {
        mysg.elem = ep
    }
    gp.waiting = mysg
    c.recvq.enqueue(mysg)
    semrelease(&c.lock, false)
    return true, true
}
```

## 四、面试高频题

### Q1: Channel底层如何实现？

```
A:
1. 环形队列存储数据
2. 等待队列管理goroutine
3. 锁机制保证安全
```

### Q2: 有缓冲和无缓冲Channel区别？

```
A:
• 无缓冲: 同步，必须同时send和receive
• 有缓冲: 异步，缓冲区满才阻塞
```

## 五、自测题

1. 解释Channel内存布局
2. 如何实现select语句？
3. 如何处理Channel泄漏？

---

## 参考文档

- [Go源码chan.go](https://github.com/golang/go/blob/master/src/runtime/chan.go)
- [Go并发编程详解](https://github.com/golang/go/wiki/Channels)
