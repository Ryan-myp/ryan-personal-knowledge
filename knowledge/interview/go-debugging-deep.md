# Go调试技巧深度实现 - 资深专家

## 一、调试工具链

### 1.1 Delve专业调试器

```go
// Delve调试器使用
// 安装: go install github.com/go-delve/delve/cmd/dlv@latest

package main

import (
    "fmt"
    "log"
)

func main() {
    data := []int{1, 2, 3, 4, 5}
    result := processData(data)
    fmt.Println(result)
}

func processData(data []int) int {
    sum := 0
    for _, v := range data {
        sum += v
    }
    return sum
}
```

```bash
# 启动调试
dlv debug main.go

# 连接正在运行的进程
dlv attach <pid>

# 调试单元测试
dlv test ./...

# 常用命令
break main.go:25           # 设置断点
continue                   # 继续执行
next                       # 单步跳过
step                       # 单步进入
stepinto                   # 进入函数内部
finish                     # 执行到函数结束
print varName              # 打印变量
locals                     # 显示局部变量
goroutines                 # 显示所有协程
goroutine 1                # 切换到指定协程
bt                         # 查看调用栈
watch varName              # 设置观察点
condition 1 expr           # 条件断点
```

### 1.2 Race Detector并发检测

```go
package debug

import (
    "sync"
    "testing"
)

// 竞态条件示例
func TestRaceCondition(t *testing.T) {
    var counter int
    var wg sync.WaitGroup
    
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            counter++ // 竞态条件！
        }()
    }
    
    wg.Wait()
    t.Logf("counter: %d", counter)
}

// 竞态检测运行
// go test -race ./...
// go run -race main.go
```

```go
// 安全的并发计数器
type SafeCounter struct {
    mu      sync.Mutex
    counter int
}

func (c *SafeCounter) Inc() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.counter++
}

func (c *SafeCounter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.counter
}
```

## 二、pprof性能分析

### 2.1 内存分析

```go
package profile

import (
    "fmt"
    "net/http"
    _ "net/http/pprof"
    "runtime"
)

func main() {
    // 启动pprof HTTP端点
    go func() {
        http.ListenAndServe("localhost:6060", nil)
    }()
    
    // 触发GC
    runtime.GC()
    
    // 获取内存profile
    p := runtime.MemProfile{}
    runtime.ReadMemProfile(&p)
    
    fmt.Printf("Alloc = %v MiB\n", toMiB(p.TotalAlloc))
    fmt.Printf("Sys = %v MiB\n", toMiB(p.Sys))
    fmt.Printf("Lookups = %v\n", p.Lookups)
    fmt.Printf("Mallocs = %v\n", p.Mallocs)
    fmt.Printf("Frees = %v\n", p.Frees)
}

func toMiB(bytes uint64) uint64 {
    return bytes / 1024 / 1024
}
```

```bash
# 查看内存分布
go tool pprof http://localhost:6060/debug/pprof/heap

# 查看分配热点
top 10

# 生成火焰图
web

# 查看特定函数调用
list processData
```

### 2.2 Goroutine分析

```go
package profile

import (
    "fmt"
    "runtime"
)

func main() {
    // 获取goroutine数量
    fmt.Printf("Goroutines: %d\n", runtime.NumGoroutine())
    
    // 获取goroutine stack profile
    p := make([]byte, 64*1024)
    n := runtime.Stack(p, true)
    fmt.Printf("Stack trace:\n%s\n", p[:n])
}
```

```bash
# 查看goroutine数量
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 查看死锁
goroutine 1 [running]:
goroutine 2 [chan send]:

# 查看阻塞详情
go tool pprof http://localhost:6060/debug/pprof/block
```

### 2.3 CPU分析

```go
package profile

import (
    "fmt"
    "runtime/pprof"
)

func main() {
    // 创建CPU profile文件
    f, err := os.Create("cpu.prof")
    if err != nil {
        log.Fatal(err)
    }
    defer f.Close()
    
    // 启动profiling
    pprof.StartCPUProfile(f)
    defer pprof.StopCPUProfile()
    
    // 执行被分析的代码
    result := processData()
    fmt.Println(result)
}

func processData() int {
    sum := 0
    for i := 0; i < 1000000; i++ {
        sum += i
    }
    return sum
}
```

```bash
# 分析CPU profile
go tool pprof cpu.prof

# 查看耗时最多的函数
top

# 生成火焰图
go tool pprof -http=:8080 cpu.prof
```

## 三、并发调试

### 3.1 死锁检测

```go
package debug

import (
    "sync"
    "time"
)

// 死锁示例
func deadlockExample() {
    var mu1, mu2 sync.Mutex
    
    var wg sync.WaitGroup
    wg.Add(2)
    
    go func() {
        defer wg.Done()
        mu1.Lock()
        time.Sleep(100 * time.Millisecond)
        mu2.Lock() // 死锁！mu2被另一个goroutine持有
        mu2.Unlock()
        mu1.Unlock()
    }()
    
    go func() {
        defer wg.Done()
        mu2.Lock()
        mu1.Lock() // 死锁！mu1被另一个goroutine持有
        mu1.Unlock()
        mu2.Unlock()
    }()
    
    wg.Wait()
}

// 避免死锁的策略
func deadlockAvoidance() {
    var mu1, mu2 sync.Mutex
    
    var wg sync.WaitGroup
    wg.Add(2)
    
    // 始终按相同顺序获取锁
    go func() {
        defer wg.Done()
        mu1.Lock()
        defer mu1.Unlock()
        
        time.Sleep(100 * time.Millisecond)
        
        mu2.Lock()
        defer mu2.Unlock()
    }()
    
    go func() {
        defer wg.Done()
        mu1.Lock()
        defer mu1.Unlock()
        
        mu2.Lock()
        defer mu2.Unlock()
    }()
    
    wg.Wait()
}
```

### 3.2 Context取消调试

```go
package debug

import (
    "context"
    "fmt"
    "time"
)

func contextDebug() {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    
    // 监控context取消
    go func() {
        select {
        case <-ctx.Done():
            fmt.Printf("context canceled: %v\n", ctx.Err())
        }
    }()
    
    // 模拟长时间操作
    select {
    case <-ctx.Done():
        fmt.Println("operation timeout")
    case <-time.After(10 * time.Second):
        fmt.Println("operation completed")
    }
}
```

## 四、常见并发问题排查

### 4.1 Goroutine泄漏

```go
package debug

import (
    "runtime"
    "sync"
    "time"
)

// Goroutine泄漏示例
func goroutineLeakExample() {
    ch := make(chan int)
    
    // 启动goroutine等待发送
    go func() {
        <-ch // 永远不会收到值
    }()
    
    time.Sleep(100 * time.Millisecond)
    fmt.Printf("goroutines: %d\n", runtime.NumGoroutine())
}

// 修复方案：使用带缓冲的channel或context
func goroutineLeakFix() {
    ch := make(chan int, 1)
    
    go func() {
        select {
        case ch <- 1:
        case <-time.After(time.Second):
        }
    }()
    
    time.Sleep(100 * time.Millisecond)
    fmt.Printf("goroutines: %d\n", runtime.NumGoroutine())
}
```

### 4.2 Channel阻塞

```go
package debug

import (
    "fmt"
    "time"
)

// Channel阻塞检测
func channelBlockingDetect() {
    ch := make(chan int)
    
    done := make(chan bool)
    
    // 启动监控goroutine
    go func() {
        select {
        case <-ch:
            fmt.Println("received value")
        case <-time.After(5 * time.Second):
            fmt.Println("channel blocked for 5 seconds")
            done <- true
        }
    }()
    
    <-done
}
```

## 五、生产环境调试

### 5.1 结构化日志

```go
package debug

import (
    "log/slog"
    "os"
)

func setupLogger() *slog.Logger {
    handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
        Level: slog.LevelDebug,
    })
    return slog.New(handler)
}

func main() {
    logger := setupLogger()
    
    logger.Info("application started",
        slog.String("version", "1.0.0"),
        slog.Int("port", 8080),
    )
    
    logger.Debug("processing request",
        slog.String("method", "GET"),
        slog.String("path", "/api/users"),
        slog.Duration("duration", 50*time.Millisecond),
    )
}
```

### 5.2 错误处理

```go
package debug

import (
    "fmt"
    "runtime"
)

// 带堆栈跟踪的错误
type ErrorWithStack struct {
    Message string
    Stack   string
}

func NewError(message string) error {
    stack := make([]byte, 4096)
    n := runtime.Stack(stack, false)
    
    return &ErrorWithStack{
        Message: message,
        Stack:   string(stack[:n]),
    }
}

func (e *ErrorWithStack) Error() string {
    return e.Message
}

func (e *ErrorWithStack) StackTrace() string {
    return e.Stack
}
```

## 六、面试高频题

### Q1: 如何使用Delve调试？

```
A:
1. 安装: go install github.com/go-delve/delve/cmd/dlv@latest
2. 启动: dlv debug main.go
3. 设置断点: break main.go:25
4. 执行: continue
5. 单步: next / step / stepinto
6. 查看变量: print varName
7. 查看调用栈: bt
```

### Q2: 如何检测竞态条件？

```
A:
1. 使用-race标志: go run -race main.go
2. 使用test: go test -race ./...
3. 分析race detector输出
4. 添加同步机制（mutex/channel）
```

### Q3: 如何调试goroutine泄漏？

```
A:
1. 使用runtime.NumGoroutine()监控
2. 使用pprof分析goroutine profile
3. 检查channel是否有receiver/sender
4. 确保goroutine能正常退出
5. 使用context控制生命周期
```

## 七、自测题

1. 解释pprof的heap/goroutine/cpu profile区别
2. 如何使用Delve调试并发代码？
3. 如何检测和修复goroutine泄漏？
4. 生产环境调试的最佳实践？

---

## 参考文档

- [Delve官方文档](https://github.com/go-delve/delve)
- [Go Race Detector](https://go.dev/doc/race)
- [pprof文档](https://pkg.go.dev/runtime/pprof)
- [Go调试指南](https://go.dev/doc/debug)
