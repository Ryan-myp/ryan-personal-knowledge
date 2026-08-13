# 日志聚合系统 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   EFK 日志聚合架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   应用层                采集层                存储层              展示层  │
│   ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐ │
│   │ App     │───────►│ Fluentd │───────►│ Elastic │───────►│ Kibana  │ │
│   │ 日志    │        │ 收集    │        │ 存储    │        │ 可视化  │ │
│   └─────────┘        └─────────┘        └─────────┘        └─────────┘ │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package logging

import (
    "context"
    "github.com/fluent/fluent-operator/apis/fluentbit/v1alpha2"
)

// LoggingCollector 日志采集器
type LoggingCollector struct {
    client *K8sClient
}

// FluentdConfig Fluentd配置
type FluentdConfig struct {
    Namespace     string
    Inputs        []InputConfig
    Outputs       []OutputConfig
}

type InputConfig struct {
    Type      string
    Tag       string
    Path      string
    Position  bool
}

type OutputConfig struct {
    Type      string
    Host      string
    Port      int
    Index     string
}

// CreateLoggingStack 创建日志栈
func (c *LoggingCollector) CreateLoggingStack(ctx context.Context, config FluentdConfig) error {
    // 创建FluentBit
    fluentbit := &v1alpha2.FluentBit{
        ObjectMeta: metav1.ObjectMeta{
            Name:      "fluentbit",
            Namespace: config.Namespace,
        },
        Spec: v1alpha2.FluentBitSpec{
            Config: &v1alpha2.FluentBitConfig{
                Inputs: config.Inputs,
                Outputs: config.Outputs,
            },
        },
    }
    
    // 创建Fluentd
    fluentd := &v1alpha2.Fluentd{
        ObjectMeta: metav1.ObjectMeta{
            Name:      "fluentd",
            Namespace: config.Namespace,
        },
        Spec: v1alpha2.FluentdSpec{
            Config: &v1alpha2.FluentdConfig{
                Outputs: config.Outputs,
            },
        },
    }
    
    return c.client.Create(ctx, fluentbit, fluentd)
}
```

## 三、面试高频题

### Q1: 如何设计日志系统？

```
A:
1. 采集方案
2. 存储方案
3. 查询方案
```

### Q2: 如何解决日志丢失？

```
A:
1. 本地缓冲
2. 重试机制
3. 持久化队列
```

## 四、自测题

1. 解释EFK架构
2. 如何配置采集？
3. 如何解决丢失？

---

## 参考文档

- [EFK Stack](https://www.elastic.co/elastic-stack)
- [Fluentd](https://docs.fluentd.org/)
