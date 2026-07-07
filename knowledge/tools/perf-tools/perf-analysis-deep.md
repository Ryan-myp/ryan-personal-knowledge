# 性能分析工具实战指南

## 一、入门引导

性能分析（Profiling）是定位性能瓶颈的关键手段。好的性能分析能让你快速找到 CPU、内存、IO 的瓶颈点。

### 1.1 性能分析流程

```
采集数据 → 分析热点 → 定位瓶颈 → 优化验证
```

### 1.2 常用工具对比

| 工具 | 语言 | 用途 | 精度 |
|------|------|------|------|
| pprof | Go | CPU/内存/协程 | 高 |
| flamegraph | 多语言 | 调用栈可视化 | 高 |
| valgrind | C/C++ | 内存/性能 | 高 |
| perf | Linux | 内核级性能 | 极高 |
| py-spy | Python | 采样分析 | 中 |
| async-profiler | JVM | Java 性能 | 高 |

## 二、Go 性能分析

### 2.1 CPU Profiling

```go
package main

import (
    "os"
    "runtime/pprof"
)

func main() {
    // 创建 CPU profile 文件
    f, _ := os.Create("cpu.prof")
    pprof.StartCPUProfile(f)
    defer pprof.StopCPUProfile()
    
    // 你的业务逻辑
    doWork()
}
```

```bash
# 分析 CPU profile
go tool pprof -http=:8081 cpu.prof

# 文本模式
go tool pprof -text cpu.prof

# 拓扑模式
go tool pprof -top cpu.prof
```

### 2.2 内存 Profiling

```go
// 设置内存 profile 频率
runtime.MemProfileRate = 1 << 20  // 每 1MB 采样一次
```

```bash
# heap profile
go tool pprof -http=:8081 -alloc_space myapp

# inuse_space
go tool pprof -http=:8081 -inuse_space myapp

# 比较两次内存快照
go tool pprof -http=:8081 -base old.prof new.prof
```

### 2.3 Goroutine Profiling

```bash
# 查看 goroutine 数量
go tool pprof -http=:8081 goroutine myapp

# 查看 goroutine 泄漏
go tool pprof -http=:8081 -sample_index=goroutine myapp
```

### 2.4 Trace 分析

```go
import "runtime/trace"

func main() {
    f, _ := os.Create("trace.out")
    trace.Start(f)
    defer trace.Stop()
    
    // 业务逻辑
    doWork()
}
```

```bash
# 可视化 trace
go tool trace trace.out
# 浏览器打开 http://localhost:8081/debug/trace
```

## 三、火焰图分析

### 3.1 生成火焰图

```bash
# 1. 采样
perf record -F 99 -g -- ./myapp

# 2. 生成火焰图
perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg

# 3. 浏览器打开
open flame.svg
```

### 3.2 解读火焰图

- **宽度**：表示 CPU 占用比例
- **高度**：表示调用栈深度
- **颜色**：随机分配，无特殊含义

## 四、自测题

### 4.1 选择题

1. pprof 中，`-alloc_space` 和 `-inuse_space` 的区别是什么？
   - A) 前者分配总量，后者当前使用量
   - B) 前者当前使用量，后者分配总量
   - C) 两者一样
   - D) 前者分析 CPU，后者分析内存

### 4.2 编程题

1. 为一个 Go 服务添加完整的性能分析支持

## 五、动手验证

```bash
# 1. 创建一个测试程序
cat > bench.go << 'EOF'
package main

import (
    "fmt"
    "runtime/pprof"
    "os"
)

func main() {
    f, _ := os.Create("bench.prof")
    pprof.WriteHeapProfile(f)
    f.Close()
    
    fmt.Println("Profile saved to bench.prof")
}
EOF

# 2. 运行并分析
go run bench.go
go tool pprof -http=:8081 bench.prof
```
