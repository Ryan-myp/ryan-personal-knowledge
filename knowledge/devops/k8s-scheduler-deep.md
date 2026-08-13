# K8s调度器深入 - 资深专家深度实现

## 一、调度流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       K8s调度流程                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. Watch API                                                           │
│   └── 监听Pod创建事件                                                     │
│                                                                         →
│   2. Predicate (过滤)                                                      │
│   └── 移除不满足条件的节点                                                  │
│       ├── 资源充足                                                           │
│       ├── 亲和性匹配                                                         │
│       └── 无冲突                                                              │
│                                                                         →
│   3. Priority (优先级)                                                    │
│   └── 计算每个节点得分                                                      │
│       ├── 资源打分                                                           │
│       ├── 亲和性打分                                                         │
│       └── 污点容忍                                                           │
│                                                                         →
│   4. Bind (绑定)                                                          │
│   └── 将Pod绑定到选定节点                                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Predicate实现

```go
func NodeResourcesFit(pod *v1.Pod, meta *predCtx, nodeInfo *schedulercache.NodeInfo) *Status {
    requested := getResourceRequests(pod)
    allocatable := nodeInfo.Allocatable()
    
    // 检查资源
    for resourceName, req := range requested {
        if req > allocatable[resourceName] {
            return NewStatus(Unschedulable, "insufficient resources")
        }
    }
    
    // 检查污点
    for _, taint := range nodeInfo.Node().Spec.Taints {
        if !podToleratesTaint(pod, &taint) {
            return NewStatus(Unschedulable, "taint not tolerated")
        }
    }
    
    return Success
}
```

## 三、面试高频题

### Q1: 调度器如何工作？

```
A:
1. Watch Pod事件
2. Predicate过滤
3. Priority打分
4. Bind绑定
```

### Q2: 如何实现自定义调度？

```
A:
1. 编写Plugin
2. 注册调度器
3. 配置策略
```

## 四、自测题

1. 解释调度流程
2. 如何实现Predicate？
3. 如何优化调度性能？

---

## 参考文档

- [K8s调度器源码](https://github.com/kubernetes/kubernetes/tree/master/pkg/scheduler)
- [Scheduler插件开发](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduler-extender/)
