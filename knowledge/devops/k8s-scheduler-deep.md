# Kubernetes调度器 - 资深专家深度实现

## 一、调度流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scheduler │────►│   PreFilter │────►│    Filter   │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                                      │
       │    ┌─────────────┐                   │
       └────│ PostFilter  │◄──────────────────┘
            └─────────────┘
                  │
            ┌─────▼─────┐
            │   Score   │
            └─────┬─────┘
                  │
            ┌─────▼─────┐
            │   Bind    │
            └─────┬─────┘
                  │
            ┌─────▼─────┐
            │  Assign   │
            └───────────┘
```

## 二、调度插件

```go
package scheduler

type Plugin interface {
    Name() string
    PreSchedule(ctx context.Context, cycleState *CycleState, pod *v1.Pod) *Status
    Schedule(ctx context.Context, cycleState *CycleState, pod *v1.Pod, nodes []*v1.Node) (*v1.Node, *Status)
    PostSchedule(ctx context.Context, cycleState *CycleState, pod *v1.Pod, nodeName string) *Status
}

type NodeSelector struct{}
func (p *NodeSelector) Schedule(ctx context.Context, cs *CycleState, pod *v1.Pod, nodes []*v1.Node) (*v1.Node, *Status) {
    for _, node := range nodes {
        if fits(pod, node) {
            return node, NewStatus(Success)
        }
    }
    return nil, NewStatus(Unschedulable)
}
```

## 三、资源限制

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: example
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
      limits:
        cpu: "500m"
        memory: "256Mi"
```

## 四、面试高频题

### Q1: K8s调度器工作原理？

```
A:
1. 预选阶段: 过滤不符合条件的节点
2. 优选阶段: 给符合节点打分
3. 绑定阶段: 选择最优节点
```

### Q2: 如何实现自定义调度器？

```
A:
1. 实现Plugin接口
2. 注册到调度框架
3. 配置优先级
```

## 五、自测题

1. 解释调度器工作流程
2. 如何实现资源隔离？
3. 如何优化调度性能？

---

## 参考文档

- [Kubernetes源码](https://github.com/kubernetes/kubernetes/tree/master/pkg/scheduler)
- [K8s调度器文档](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduler-extender/)
