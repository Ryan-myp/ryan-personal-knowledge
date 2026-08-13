# K8s调度器 - 资深专家深度实现

## 一、调度流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      K8s调度器流程                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Pod Created                                                            │
│        │                                                                 │
│        ▼                                                                 │
│   Scheduler                                                              │
│   ├── Filtering (预选)                                                    │
│   │   ├── NodeAffinity                                                   │
│   │   ├── ResourceRequirements                                           │
│   │   ├── TaintTolerance                                                 │
│   │   └── PodAffinity                                                    │
│   │                                                                      │
│   ├── Scoring (优选)                                                     │
│   │   ├── LeastRequestedPriority                                         │
│   │   ├── BalancedResourceAllocation                                   │
│   │   └── ImageLocalityPriority                                          │
│   │                                                                      │
│   └── Binding                                                            │
│        │                                                                 │
│        ▼                                                                 │
│   API Server                                                              │
│        │                                                                 │
│        ▼                                                                 │
│   Node                                                                   │
│   ├── kubelet                                                            │
│   ├── container runtime                                                  │
│   └── network setup                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、预选逻辑

```go
func (sched *Scheduler) filterPod(pod *v1.Pod, node *v1.Node) ([]*v1.Node, error) {
    var filteredNodes []*v1.Node
    
    for _, node := range allNodes {
        // 资源检查
        if !sched.resourcesFit(pod, node) {
            continue
        }
        
        // 亲和性检查
        if !sched.affinityCheck(pod, node) {
            continue
        }
        
        // 污点检查
        if !sched.taintCheck(node, pod) {
            continue
        }
        
        filteredNodes = append(filteredNodes, node)
    }
    
    return filteredNodes, nil
}
```

## 三、优选策略

```go
func (sched *Scheduler) scoreNodes(nodes []*v1.Node, pod *v1.Pod) (map[*v1.Node]int, error) {
    scores := make(map[*v1.Node]int)
    
    for _, node := range nodes {
        score := 0
        
        // 资源利用率（越低越好）
        resourceScore := sched.resourceScore(node, pod)
        score += resourceScore
        
        // 镜像本地化（越高越好）
        imageScore := sched.imageLocalScore(node, pod)
        score += imageScore
        
        scores[node] = score
    }
    
    return scores, nil
}
```

## 四、面试高频题

### Q1: K8s调度器如何工作？

```
A:
1. 预选阶段
2. 优选阶段
3. 绑定阶段
```

### Q2: 如何自定义调度器？

```
A:
1. 扩展Scheduler框架
2. 编写插件
3. 配置调度策略
```

## 五、自测题

1. 解释调度流程
2. 如何实现自定义调度器？
3. 如何优化调度性能？

---

## 参考文档

- [K8s源码](https://github.com/kubernetes/kubernetes)
- [Scheduler插件](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduler-extender/)
