# Lookalike人群拓展

> **类型**: 人群拓展
> **难度**: 专家级
> **最后更新**: 2026-08-12

---

## 1. 背景

这是关于Lookalike人群拓展的实战案例。

### 1.1 业务场景

| 属性 | 值 |
|------|-----|
| **场景类型** | 生产环境问题 |
| **影响范围** | 核心业务 |
| **发现时间** | 2024-XX-XX |
| **处理时长** | 4小时 |

### 1.2 系统架构

```
+---------------------------------------------------------------+
|                     系统架构图                               |
+---------------------------------------------------------------+
|                                                               |
|  ┌──────────┐    ┌──────────┐    ┌──────────┐               |
|  │  Client  │───▶│ Gateway  │───▶│ Service  │               |
|  └──────────┘    └──────────┘    └────┬─────┘               |
|                                       │                      |
|                                  ┌────┴─────┐               |
|                                  │ Database │               |
|                                  └──────────┘               |
|                                                               |
+---------------------------------------------------------------+

---

## 2. 问题描述

### 人群拓展现象

| 指标 | 正常值 | 异常值 |
|------|--------|--------|
| QPS | 10,000 | 2,000 |
| P99延迟 | 10ms | 500ms |
| 错误率 | 0.01% | 5% |
| 内存使用 | 4GB | 12GB |

### 2.1 告警信息

```
ALERT: HighMemoryUsage
  Instance: prod-ad-server-01
  Value: 95%
  Threshold: 80%
  Timestamp: 2024-08-12T10:30:00Z
```

---

## 3. 排查过程

### 3.1 第一步：收集诊断信息

```bash
# 查看系统资源
top -p $(pgrep ad-server)

# 查看内存分配
go tool pprof http://localhost:6060/debug/pprof/heap

# 查看goroutine
curl http://localhost:6060/debug/pprof/goroutine?debug=1
```

### 3.2 第二步：定位根因

**发现**: Goroutine泄漏导致内存持续增长

```go
// 问题代码
func processRequests() {
    for {
        select {
        case req := <-requestChan:
            go handleRequest(req)  // 每次创建新goroutine
        }
    }
}
```

---

## 4. 解决方案

### 4.1 临时方案

```bash
# 重启服务释放内存
systemctl restart ad-server

# 增加监控频率
export PROMETHEUS_SCRAPE_INTERVAL=10s
```

### 4.2 根本修复

```go
// 使用Worker Pool替代动态创建goroutine
type WorkerPool struct {
    tasks   chan *Request
    results chan *Response
    wg      sync.WaitGroup
}

func (wp *WorkerPool) Start(n int) {
    for i := 0; i < n; i++ {
        wp.wg.Add(1)
        go func() {
            defer wp.wg.Done()
            for req := range wp.tasks {
                wp.handle(req)
            }
        }()
    }
}
```

---

## 5. 效果验证

| 指标 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| QPS | 2,000 | 10,000 | 5x |
| P99延迟 | 500ms | 10ms | 50x |
| 内存使用 | 12GB | 4GB | 3x |
| 错误率 | 5% | 0.01% | 500x |

---

## 6. 经验总结

### 6.1 经验

1. **goroutine泄漏**是内存问题的常见原因，应使用Worker Pool模式
2. **监控告警**要及时，设置合理的阈值
3. **定期分析**heap profile，发现潜在问题

### 6.2 教训

1. 未及时监控goroutine数量变化
2. 没有设置内存使用阈值告警
3. 测试环境未能复现生产问题

---

**文档版本**: v1.0
**作者**: Expert Engineer
**审核**: Tech Lead