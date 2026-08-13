# 性能压测实战 - 资深专家深度实现

## 一、压测工具对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    性能压测工具对比                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   工具                | 特点                    | 适用场景             │
│   ────────────────────┼─────────────────────────┼──────────────────────│
│   k6                  | JavaScript脚本         | API压测              │
│   Gatling             | Scala脚本            | 高并发场景           │
│   JMeter              | GUI配置              | 复杂场景             │
│   wrk                 | Lua脚本              | HTTP性能测试         │
│   hey                 | 简单易用             | 快速测试             │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、k6实现

```go
package load_test

import (
    "github.com/k6io/k6/js/common"
    "github.com/k6io/k6/lib"
    "github.com/k6io/k6/stats"
)

// Options k6选项
var Options = struct {
    VUs  uint64 `json:"vus"`
    Duration string `json:"duration"`
}{
    VUs: 100,
    Duration: "10m",
}

// Default export default function() {
    const res = http.get("https://api.example.com/health")
    
    // 自定义指标
    stats.PushIfNotRegistered("response_time", stats.NewTimerData())
    
    // 检查响应
    if res.status != 200 {
        throw new Error("non-200 status")
    }
    
    // 记录指标
    stats.Record(group.context(), "response_time", res.time.Milliseconds())
}

// Group 压力组
type Group struct {
    Name string
    VUs  uint64
}

func (g *Group) Run() *Result {
    // 执行压测
    result := Execute(g.Name, g.VUs)
    
    // 收集指标
    metrics := collectMetrics(result)
    
    return &Result{
        Metrics: metrics,
        Passed:  metrics.ErrorRate < 0.01,
    }
}
```

## 三、面试高频题

### Q1: 如何进行性能压测？

```
A:
1. 确定指标
2. 逐步加压
3. 分析结果
```

### Q2: 如何判断性能瓶颈？

```
A:
1. CPU/内存使用
2. 响应时间分布
3. 错误率趋势
```

## 四、自测题

1. 解释压测流程
2. 如何实现k6测试？
3. 如何分析结果？

---

## 参考文档

- [k6 Docs](https://k6.io/docs/)
- [Gatling](https://gatling.io/)
