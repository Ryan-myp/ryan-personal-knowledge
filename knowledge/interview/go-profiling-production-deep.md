# Go性能剖析 - 资深专家深度实现

## 一、pprof工具

### 1.1 开启pprof

```go
package main

import (
	_ "net/http/pprof"
)

func main() {
	go func() {
		http.ListenAndServe("localhost:6060", nil)
	}()
	// 业务逻辑
}
```

### 1.2 常用命令

```bash
# CPU profiling
go tool pprof http://localhost:6060/debug/pprof/profile

# Memory profiling
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine profiling
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Block profiling
go tool pprof http://localhost:6060/debug/pprof/block
```

## 二、性能分析

### 2.1 CPU分析

```bash
# 生成SVG可视化
go tool pprof -http=:8080 pprof.exec
# 或者
go tool pprof -pdf pprof.exec > profile.pdf
```

```go
// 基准测试
func BenchmarkSort(b *testing.B) {
	data := generateData(1000)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sort.Ints(data)
	}
}
```

### 2.2 内存分析

```bash
# 检查内存泄漏
go tool pprof -alloc_space http://localhost:6060/debug/pprof/heap

# 检查当前内存使用
go tool pprof -inuse_space http://localhost:6060/debug/pprof/heap
```

## 三、优化技巧

### 3.1 减少分配

```go
// ❌ 每次分配新切片
func BadExample() []byte {
	return make([]byte, 1024)
}

// ✅ 复用缓冲区
var buffer = make([]byte, 1024)
func GoodExample() []byte {
	return buffer
}
```

### 3.2 对象池

```go
package pool

import "sync"

type BufferPool struct {
	pool sync.Pool
}

func NewBufferPool() *BufferPool {
	return &BufferPool{
		pool: sync.Pool{
			New: func() interface{} {
				return make([]byte, 4096)
			},
		},
	}
}

func (p *BufferPool) Get() []byte {
	return p.pool.Get().([]byte)
}

func (p *BufferPool) Put(buf []byte) {
	p.pool.Put(buf)
}
```

### 3.3 避免逃逸

```go
// ❌ 逃逸到堆
func EscapeExample() {
	s := make([]int, 1000)
	// 大量分配
}

// ✅ 栈上分配
func StackExample() []int {
	var s [1000]int
	return s[:]
}
```

## 四、竞态检测

```bash
# 启动竞态检测
go test -race ./...

# 运行检测
go run -race main.go
```

```go
package race

import (
	"sync"
	"testing"
)

func TestConcurrent(t *testing.T) {
	var mu sync.Mutex
	var count int
	
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			mu.Lock()
			count++
			mu.Unlock()
		}()
	}
	wg.Wait()
	
	if count != 100 {
		t.Errorf("expected 100, got %d", count)
	}
}
```

## 五、trace工具

```bash
# 生成trace
go tool trace profile.out

# 在浏览器中查看
go tool trace -http=:8080 profile.out
```

```go
package trace

import (
	"os"
	"runtime/trace"
)

func main() {
	f, _ := os.Create("trace.out")
	defer f.Close()
	
	trace.Start(f)
	defer trace.Stop()
	
	// 业务逻辑
}
```

## 六、面试高频题

### Q1: 如何进行Go性能优化？

```
A:
1. 使用pprof定位瓶颈
2. 减少内存分配
3. 优化算法复杂度
4. 合理使用并发
```

### Q2: 什么是GOMAXPROCS？

```
A: 控制并发执行的OS线程数，默认为CPU核数。
```

## 七、自测题

1. 如何使用pprof分析内存泄漏？
2. 解释sync.Pool的使用场景。

---

## 参考文档

- [Go pprof文档](https://pkg.go.dev/net/http/pprof)
