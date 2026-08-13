# Go性能分析实战 - 资深专家深度实现

## 一、分析工具

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Go 性能分析工具链                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   工具                | 用途                    | 命令                  │
│   ────────────────────┼─────────────────────────┼──────────────────────│
│   pprof              | CPU/内存/Goroutine分析   │ go tool pprof        │
│   trace              | 执行流程追踪             │ go tool trace        │
│   delve              | 调试器                  │ dlv debug            │
│   go test -bench     | 基准测试                │ go test -bench=.     │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package profiling

import (
    "net/http"
    _ "net/http/pprof"
    "runtime/pprof"
)

// StartProfiler 启动性能分析服务器
func StartProfiler(addr string) {
    go func() {
        http.ListenAndServe(addr, nil)
    }()
}

// CPUProfile CPU性能分析
func CPUProfile(w io.Writer) {
    pprof.StartCPUProfile(w)
    defer pprof.StopCPUProfile()
    
    // 执行被测代码
    doWork()
}

// MemoryProfile 内存分析
func MemoryProfile() {
    runtime.GC()
    
    var m runtime.MemStats
    runtime.ReadMemStats(&m)
    
    fmt.Printf("Alloc = %v MiB\n", bToMb(m.Alloc))
    fmt.Printf("TotalAlloc = %v MiB\n", bToMb(m.TotalAlloc))
    fmt.Printf("Sys = %v MiB\n", bToMb(m.Sys))
    fmt.Printf("NumGC = %v\n", m.NumGC)
}

// GoroutineDump Goroutine转储
func GoroutineDump(w io.Writer) {
    pprof.Lookup("goroutine").WriteTo(w, 0)
}
```

## 三、面试高频题

### Q1: 如何使用pprof分析CPU？

```
A:
1. 启动pprof服务器
2. 访问/profile端点
3. go tool pprof分析
```

### Q2: 如何排查Goroutine泄漏？

```
A:
1. 查看goroutine数量
2. 分析stack trace
3. 定位未退出的goroutine
```

## 四、自测题

1. 解释分析工具链
2. 如何使用pprof？
3. 如何排查泄漏？

---

## 参考文档

- [Go pprof](https://pkg.go.dev/net/http/pprof)
- [Go Performance](https://go.dev/blog/pprof)
