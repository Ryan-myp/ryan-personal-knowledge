# Go 面试题库

> **文档级别**: Level 4  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已创建

---

## 一、并发编程

### Q1: goroutine 和线程的区别？

```
区别对比:
├── 调度层级
│   ├── 线程: 内核调度 (OS Level)
│   └── goroutine: 用户态调度 (GMP Model)
│
├── 内存占用
│   ├── 线程: 2MB 栈 (固定)
│   └── goroutine: 2KB 栈 (动态扩展)
│
├── 创建开销
│   ├── 线程: ~1ms
│   └── goroutine: ~1μs
│
└── 数量上限
    ├── 线程: 几千
    └── goroutine: 百万级
```

### Q2: channel 底层实现？

```go
// hchan 结构
type hchan struct {
    qcount   uint           // 队列中元素总数
    dataqsz  uint           // 循环队列长度
    lock     mutex          // 锁
    buf      unsafe.Pointer // 指向数组的指针
    elemsize uint16
    closed   uint32
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 goroutine 队列
    sendq    waitq          // 等待发送的 goroutine 队列
}
```

---

## 二、参考资料

```
核心资源:
├── Go Concurrency: https://go.dev/blog/pipelines
├── Go Runtime: https://github.com/golang/go/blob/master/src/runtime/
└── Effective Go: https://go.dev/doc/effective_go
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
