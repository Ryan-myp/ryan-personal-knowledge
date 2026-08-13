# Go调试技巧 - 资深专家深度实现

## 一、调试工具

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Go 调试工具                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   工具                | 特点                                    │
│   ────────────────────┼──────────────────────────────────────────────│
│   Delve              | 专业调试器，支持断点/步进/变量查看          │
│   Print/Panic        | 基础调试输出                              │
│   Race Detector      | 并发问题检测                              │
│   Log Level          | 结构化日志                                │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Delve使用

```bash
# 启动调试
dlv debug main.go

# 设置断点
break main.go:25

# 运行
continue

# 单步执行
next / step / stepinto

# 查看变量
print varName
locals

# 查看调用栈
bt
```

## 三、Race检测

```go
package debug

import (
    "sync"
)

// 并发安全测试
func TestConcurrentSafe(t *testing.T) {
    var wg sync.WaitGroup
    counter := 0
    
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            counter++ // 竞态条件
        }()
    }
    
    wg.Wait()
    _ = counter
}
```

```bash
# 运行race检测
go run -race main.go
go test -race ./...
```

## 四、面试高频题

### Q1: 如何使用Delve？

```
A:
1. 安装dlv
2. 设置断点
3. 单步执行
```

### Q2: 如何检测竞态？

```
A:
1. race detector
2. 静态分析
3. 代码review
```

## 五、自测题

1. 解释调试工具
2. 如何使用Delve？
3. 如何检测竞态？

---

## 参考文档

- [Delve](https://github.com/go-delve/delve)
- [Go Race Detector](https://go.dev/doc/race)
