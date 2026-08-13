# Go生产环境性能剖析 - 资深专家深度实现

## 一、pprof工具

```bash
# 启动HTTP服务暴露profile
import _ "net/http/pprof"
http.ListenAndServe("localhost:6060", nil)

# 采集CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# 采集内存profile
go tool pprof http://localhost:6060/debug/pprof/heap

# 采集goroutine profile
go tool pprof http://localhost:6060/debug/pprof/goroutine
```

## 二、常见瓶颈

### 2.1 CPU密集型

```go
// 问题代码
func ProcessData(data []int) []int {
    result := make([]int, 0, len(data))
    for _, v := range data {
        result = append(result, v*2)
    }
    return result
}

// 优化: 预分配容量
func ProcessData(data []int) []int {
    result := make([]int, len(data))
    for i, v := range data {
        result[i] = v * 2
    }
    return result
}
```

### 2.2 内存泄漏

```go
// 问题: 全局缓存无限增长
var cache = make(map[string]string)

func Get(key string) string {
    if val, ok := cache[key]; ok {
        return val
    }
    cache[key] = queryDB(key)
    return cache[key]
}

// 修复: 使用LRU缓存
import "github.com/hashicorp/golang-lru"

lru, _ := lru.New(1000)
```

## 三、面试高频题

### Q1: 如何进行Go性能分析？

```
A: 使用pprof工具，采集CPU/内存/Goroutine profile。
```

### Q2: 常见的性能瓶颈有哪些？

```
A:
1. 频繁内存分配
2. Goroutine泄漏
3. 锁竞争
4. 不必要的GC
```

## 四、自测题

1. 如何使用pprof定位性能问题？
2. 如何优化GC压力？

---

## 参考文档

- [Go pprof文档](https://pkg.go.dev/net/http/pprof)
