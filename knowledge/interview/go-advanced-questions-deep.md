# Go 进阶面试题库

> 深入 Go 进阶知识点：GMP 调度器、GC、Channel、Map、反射。
> 适用对象：Go 开发者、面试准备者

---

## 1. GMP 调度器

### Q: 请描述 Go 的 GMP 调度模型

```
G (Goroutine): 协程，包含栈、PC、状态等
M (Machine): OS 线程，执行 G 的代码
P (Processor): 逻辑处理器，维护本地队列，绑定 M

调度流程:
1. G 创建 → 放入 P 本地队列
2. P 调度 G 到 M 执行
3. 系统调用 → M 阻塞，P 寻找新 M
4. 网络 I/O → G 阻塞，P 执行其他 G
5. 时间片用完 → G 放回队列，P 调度下一个 G
```

### Q: Golang 是如何实现异步非阻塞的系统调用？

```go
// syscall 阻塞时:
// 1. M 绑定 P，执行系统调用
// 2. 如果阻塞，P 释放，寻找新 M
// 3. 系统调用返回后，G 重新入队

runtime.call18  // 系统调用入口
runtime.exitsyscall  // 释放 P
runtime.enterysyscall  // 获取 P
```

---

## 2. 内存管理

### Q: Go GC 的工作原理是什么？

```
三色标记清除算法:

白格: 未被扫描，可能可达
灰格: 已被扫描，其引用对象未全部扫描
黑格: 已被扫描，其引用对象已全部扫描

写屏障 (Write Barrier):
- 混合写屏障: 记录从黑格到白格的指针写操作
- 确保 GC 期间并发的正确性

分代收集 (Go 1.8+):
- 年轻代: 存活时间短的对象
- 老年代: 存活时间长的对象
```

### Q: 如何优化 Go 程序的内存使用？

```go
// 1. 使用 sync.Pool 减少分配
var bufPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 4096)
    },
}

// 2. 预分配 slice 容量
slice := make([]int, 0, 1000)

// 3. 避免大对象分配 (>32KB 直接分配，不经过 mcache)
// 4. 使用 string Intern 减少重复字符串
```

---

## 3. Channel 深度

### Q: Channel 的实现原理是什么？

```go
type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形队列大小
    buf      unsafe.Pointer // 环形队列缓冲区
    elemsize uint16         // 元素大小
    closed   uint32         // 是否关闭
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 G 队列
    sendq    waitq          // 等待发送的 G 队列
    
    lock mutex         // 保护 hchan 结构
}
```

### Q: select 语句的工作原理？

```go
// select 随机选择一个可执行的 case
// 如果多个 case 同时就绪，随机选择一个
// 如果没有 case 就绪且有 default，执行 default
// 如果没有 case 就绪且无 default，阻塞

select {
case <-ch1:
    // 处理 ch1
case ch2 <- value:
    // 处理 ch2
default:
    // 默认处理
}
```

---

## 4. Map 实现

### Q: Map 的并发安全问题及解决方案？

```go
// ❌ 不安全
m := make(map[string]int)
go func() { m["key"] = 1 }()
go func() { m["key"] = 2 }()

// ✅ 方案1: sync.Mutex
type SafeMap struct {
    sync.RWMutex
    data map[string]int
}

// ✅ 方案2: sync.Map
m := sync.Map{}
m.Store("key", 1)
m.Load("key")

// ✅ 方案3: 分片锁
type ShardedMap struct {
    shards [16]struct {
        sync.Mutex
        data map[string]int
    }
}
```

---

## 5. 反射

### Q: 反射的原理和使用场景？

```go
import "reflect"

func reflectExample(v interface{}) {
    t := reflect.TypeOf(v)    // 获取类型
    v := reflect.ValueOf(v)   // 获取值
    
    // 遍历结构体字段
    if t.Kind() == reflect.Struct {
        for i := 0; i < t.NumField(); i++ {
            field := t.Field(i)
            value := v.Field(i)
            fmt.Printf("%s: %v\n", field.Name, value)
        }
    }
}

// 使用场景:
// 1. 序列化工具 (json.Marshal)
// 2. ORM 框架
// 3. 测试框架 (assert)
// 4. 依赖注入容器
```

---

## 6. 实践 Checklist
- [ ] 理解 GMP 调度模型
- [ ] 掌握 GC 工作原理
- [ ] 熟练使用 Channel
- [ ] 理解 Map 实现
- [ ] 掌握反射使用

**参考**: Go 源码解析、Go 官方文档
