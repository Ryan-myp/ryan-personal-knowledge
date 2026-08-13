# K8s调度器深度实现 - 资深专家深度实现

## 一、调度流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   K8s 调度器工作流程                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Pod创建        Filter(过滤)        Score(打分)       Bind(绑定)        │
│   ┌──────┐     ┌──────────┐      ┌──────────┐    ┌──────────┐          │
│   │Queue │────►│Node预选  │─────►│Node优选  │───►│Assign    │          │
│   └──────┘     │(Filter) │      │(Score)  │    │(Bind)    │          │
│                └──────────┘      └──────────┘    └────┬─────┘          │
│                                                      ▼                  │
│                                               ┌──────────────┐         │
│                                               │  AssignPod   │         │
│                                               │  etcd写入    │         │
│                                               └──────────────┘         │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、自定义调度器

```go
package scheduler

import (
    "context"
    "k8s.io/kube-scheduler/framework"
)

// CustomPlugin 自定义调度插件
type CustomPlugin struct {
    handle framework.Handle
}

var _ framework.PreFilterPlugin = &CustomPlugin{}
var _ framework.PostFilterPlugin = &CustomPlugin{}

// Name 插件名称
func (p *CustomPlugin) Name() string {
    return "CustomPlugin"
}

// PreFilter 预过滤
func (p *CustomPlugin) PreFilter(ctx context.Context, state *framework.CycleState, pod *v1.Pod) *framework.Status {
    // 自定义预过滤逻辑
    return framework.NewStatus(framework.Success, "")
}

// Filter 过滤
func (p *CustomPlugin) Filter(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeInfo *framework.NodeInfo) *framework.Status {
    node := nodeInfo.Node()
    if node == nil {
        return framework.NewStatus(framework.Unschedulable, "node not found")
    }
    
    // 检查节点资源
    if !checkResources(node, pod) {
        return framework.NewStatus(framework.Unschedulable, "insufficient resources")
    }
    
    return framework.NewStatus(framework.Success, "")
}

// Score 打分
func (p *CustomPlugin) Score(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) (int64, *framework.Status) {
    // 自定义打分逻辑
    return int64(100), framework.NewStatus(framework.Success, "")
}
```

## 三、面试高频题

### Q1: 调度器如何工作？

```
A:
1. 监听etcd获取Pod
2. Filter过滤节点
3. Score打分排序
4. Bind绑定Pod
```

### Q2: 如何编写自定义调度器？

```
A:
1. 实现Framework接口
2. 注册插件
3. 配置调度器
```

## 四、自测题

1. 解释调度流程
2. 如何实现自定义调度？
3. 如何优化调度性能？

---

## 参考文档

- [K8s Scheduler](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
- [Scheduler Framework](https://kubernetes.io/docs/reference/sig-extension/scheduler-extension/)
