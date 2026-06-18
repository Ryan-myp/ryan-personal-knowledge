# K8s 深度：调度器/控制器/网络插件源码级

> 逐行解析 Kubernetes 核心组件源码

---

## 第一部分：调度器源码深度

### Scheduler 架构

```
K8s 调度流程：
Pod 创建 → API Server → Scheduler Watch → Predicates → Priorities → Bind

1. Predicates（过滤）：剔除不符合条件的节点
   • PodFitsResources：资源足够
   • PodFitsHostPorts：端口不冲突
   • MatchNodeSelector：标签匹配
   • NoDiskConflict：磁盘不冲突
   
2. Priorities（打分）：给符合条件的节点打分
   • ResourceBalance：资源均衡分配
   • ImageLocality：镜像本地化
   • LeastRequestedPriority：最少请求优先
   • MostRequestedPriority：最多请求优先
```

### scheduler.go 源码逐行解析

```go
// Kubernetes 源码：pkg/scheduler/scheduler.go
func (sched *Scheduler) scheduleOne(ctx context.Context, cycleState *framework.CycleState) {
    // 1. 获取下一个待调度 Pod
    pod := sched.nextPod(ctx)
    if pod == nil {
        return
    }
    
    // 2. 获取所有节点
    nodes, err := sched.nodeInformer.Lister().List(labels.Everything())
    if err != nil {
        sched.permitWaitingPodsHandler.Delete(pod)
        return
    }
    
    // 3. 预处理（PreEnqueue）
    if err := sched.preEnqueue(ctx, pod); err != nil {
        return
    }
    
    // 4. 调度循环
    for {
        // 4.1 获取调度队列中的 Pod
        pod, shutdown := sched.queue.Get()
        if shutdown {
            return
        }
        
        // 4.2 执行调度
        schedulingCycleCtx, cancel := context.WithCancel(ctx)
        frameWork := sched.Framework.Clone()
        
        // 4.3 运行 PreFilter 插件
        status := sched.scheduleCycle.PreFilter(schedulingCycleCtx, frameWork, pod)
        if !status.IsSuccess() {
            sched.handleFailedPreFilter(pod, status)
            cancel()
            continue
        }
        
        // 4.4 运行 Filter 插件（Predicates）
        status = sched.scheduleCycle.Filter(schedulingCycleCtx, frameWork, pod)
        if !status.IsSuccess() {
            sched.handleFailedFilter(pod, status)
            cancel()
            continue
        }
        
        // 4.5 运行 Score 插件（Priorities）
        status = sched.scheduleCycle.Score(schedulingCycleCtx, frameWork, pod)
        if !status.IsSuccess() {
            sched.handleFailedScore(pod, status)
            cancel()
            continue
        }
        
        // 4.6 运行 Reserve 插件
        status = sched.scheduleCycle.Reserve(schedulingCycleCtx, frameWork, pod)
        if !status.IsSuccess() {
            sched.handleFailedReserve(pod, status)
            cancel()
            continue
        }
        
        // 4.7 运行 Permit 插件
        status = sched.scheduleCycle.Permit(schedulingCycleCtx, frameWork, pod)
        if !status.IsSuccess() {
            sched.handleFailedPermit(pod, status)
            cancel()
            continue
        }
        
        // 4.8 运行 Bind 插件
        status = sched.scheduleCycle.Bind(schedulingCycleCtx, frameWork, pod)
        if !status.IsSuccess() {
            sched.handleFailedBind(pod, status)
            cancel()
            continue
        }
        
        // 4.9 运行 PostBind 插件
        sched.scheduleCycle.PostBind(schedulingCycleCtx, frameWork, pod)
        
        cancel()
    }
}
```

---

## 第二部分：控制器源码深度

### Controller Manager 架构

```
K8s 控制器：
┌─────────────────────────────────────────────────────────────────────┐
│ Controller Manager                                                   │
│                                                                      │
│  ReplicationController: 维持 Pod 副本数                               │
│  DeploymentController: 管理 Deployment 滚动更新                      │
│  ReplicaSetController: 管理 ReplicaSet                               │
│  NodeController: 监控节点健康状态                                     │
│  EndpointController: 管理 Service Endpoints                          │
│  ServiceAccountController: 管理服务账号                               │
│  TokenController: 管理 ServiceAccount Token                           │
│  GarbageCollector: 垃圾回收                                          │
│  DaemonSetController: 管理 DaemonSet                                 │
│  JobController: 管理 Job/CronJob                                     │
│  PersistentVolumeController: 管理 PV/PVC                             │
│  StatefulSetController: 管理 StatefulSet                             │
└─────────────────────────────────────────────────────────────────────┘
```

### deployment_controller.go 源码逐行解析

```go
// Kubernetes 源码：pkg/controller/deployment/deployment_controller.go
func (dc *DeploymentController) syncDeployment(key string) error {
    // 1. 解析 key
    namespace, name, err := cache.SplitMetaNamespaceKey(key)
    if err != nil {
        return err
    }
    
    // 2. 获取 Deployment
    deployment, err := dc.deploymentLister.Deployments(namespace).Get(name)
    if err != nil {
        return err
    }
    
    // 3. 获取关联的 ReplicaSets
    rss, err := dc.getReplicaSetsForDeployment(deployment)
    if err != nil {
        return err
    }
    
    // 4. 获取关联的 Pods
    pods, err := dc.getPodsForReplicaSets(rss)
    if err != nil {
        return err
    }
    
    // 5. 根据策略处理
    switch deployment.Spec.Strategy.Type {
    case apps.RollingUpdateDeploymentStrategyType:
        return dc.rolloutRollingUpdate(deployment, rss, pods)
    case apps.RecreateDeploymentStrategyType:
        return dc.rolloutRecreate(deployment, rss, pods)
    }
    
    return nil
}

// rolloutRollingUpdate 滚动更新
func (dc *DeploymentController) rolloutRollingUpdate(
    deployment *apps.Deployment,
    rss []*apps.ReplicaSet,
    pods []*v1.Pod,
) error {
    // 1. 计算最大不可用和最大增量
    maxUnavailable := intstr.GetValueFromIntOrPercent(
        deployment.Spec.Strategy.RollingUpdate.MaxUnavailable,
        int(*deployment.Spec.Replicas), true)
    maxSurge := intstr.GetValueFromPercent(
        deployment.Spec.Strategy.RollingUpdate.MaxSurge,
        int(*deployment.Spec.Replicas), true)
    
    // 2. 检查当前可用副本数
    availableReplicas := dc.countAvailableReplicas(rss, pods)
    unavailable := int(*deployment.Spec.Replicas) - availableReplicas
    
    // 3. 如果不可用数超过阈值，暂停更新
    if unavailable >= maxUnavailable {
        return nil
    }
    
    // 4. 创建新的 ReplicaSet
    newRS := dc.createNewReplicaSet(deployment)
    
    // 5. 扩展新 ReplicaSet
    desiredReplicas := int32(maxSurge) + int32(*deployment.Spec.Replicas)
    currentReplicas := newRS.Status.Replicas
    if currentReplicas < desiredReplicas {
        dc.scaleReplicaSet(newRS, currentReplicas+1)
    }
    
    // 6. 缩减旧的 ReplicaSet
    for _, rs := range rss {
        if rs.UID != newRS.UID {
            dc.scaleReplicaSet(rs, rs.Status.Replicas-1)
        }
    }
    
    return nil
}
```

---

## 第三部分：网络插件源码深度

### CNI 架构

```
K8s 网络模型：
┌─────────────────────────────────────────────────────────────────────┐
│ Node 1                                                               │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│ │ Pod 1    │  │ Pod 2    │  │ Pod 3    │                          │
│ │ IP:10.0.0│  │ IP:10.0.1│  │ IP:10.0.2│                          │
│ └────┬─────┘  └────┬─────┘  └────┬─────┘                          │
│      │ eth0        │ eth0        │ eth0                            │
│      └──────┬──────┴──────┬──────┘                                │
│             │ veth pair    │                                      │
│      ┌──────┴──────┐                                      │
│      │ CNI Bridge  │ (cni0)                                 │
│      │ 10.0.0.0/24 │                                        │
│      └──────┬──────┘                                        │
│             │ br0                                            │
│      ┌──────┴──────┐                                        │
│      │ Host NIC    │ (eth0: 192.168.1.100)                   │
│      └─────────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘

Flannel 网络模型：
• Host-GW：宿主机路由（简单，不支持跨节点）
• VXLAN：Overlay 网络（支持跨节点，性能稍差）
• Direct Routing：直接路由（高性能，需要二层互通）
```

### flannel.go 源码逐行解析

```go
// Flannel 源码：backend/vxlan/vxlan.go
func (backend *vxlanBackend) Run(ctx context.Context, wg *sync.WaitGroup) error {
    // 1. 创建 VXLAN 设备
    linkAttrs := netlink.LinkAttrs{
        Name:         backend.name,
        Type:         "vxlan",
        VxlanId:      int(backend.subnet),
        VxlanPort:    8472,
        VxlanLearn:   true,
        VxlanSrcAddr: backend.l2sm.addr,
    }
    
    vxlanLink := &netlink.Vxlan{
        LinkAttrs: linkAttrs,
    }
    
    if err := netlink.LinkAdd(vxlanLink); err != nil {
        return err
    }
    
    // 2. 启动监听 goroutine
    wg.Add(1)
    go func() {
        defer wg.Done()
        backend.listen(ctx)
    }()
    
    // 3. 注册 ARP 代理
    if err := backend.registerARPProxy(); err != nil {
        return err
    }
    
    // 4. 注册 NDP 代理（IPv6）
    if err := backend.registerNDPProxy(); err != nil {
        return err
    }
    
    return nil
}

// listen 监听 VXLAN 数据包
func (backend *vxlanBackend) listen(ctx context.Context) {
    conn, err := net.ListenPacket("udp4", ":8472")
    if err != nil {
        log.Fatalf("failed to listen on UDP: %v", err)
    }
    defer conn.Close()
    
    buf := make([]byte, 65536)
    for {
        select {
        case <-ctx.Done():
            return
        default:
            n, raddr, err := conn.ReadFromUDP(buf)
            if err != nil {
                continue
            }
            
            // 解析 VXLAN 头部
            vxlanHeader := buf[0:8]
            vni := uint32(vxlanHeader[4])<<16 | 
                   uint32(vxlanHeader[5])<<8 | 
                   uint32(vxlanHeader[6])
            
            // 提取内层以太网帧
            innerFrame := buf[14:n]
            
            // 转发到对应的 Pod
            backend.forward(innerFrame, vni)
        }
    }
}

// forward 转发数据包到 Pod
func (backend *vxlanBackend) forward(frame []byte, vni uint32) {
    // 1. 解析源 MAC 地址
    srcMAC := net.HardwareAddr(frame[0:6])
    
    // 2. 查找对应的 Pod
    pod := backend.lookupPod(srcMAC)
    if pod == nil {
        return
    }
    
    // 3. 通过 veth pair 转发到 Pod
    conn, err := net.Dial("unix", fmt.Sprintf("/var/run/docker.sock"))
    if err != nil {
        return
    }
    defer conn.Close()
    
    // 4. 写入 Pod 的网络命名空间
    err = netlink.LinkSetNsFd(pod.link, int(conn.Fd()))
    if err != nil {
        return
    }
}
```

---

## 第四部分：自测题

### Q1: K8s 调度器的工作流程？

**A**: 获取 Pod → 获取节点列表 → Predicates 过滤 → Priorities 打分 → 选择最高分节点 → Bind。

### Q2: RollingUpdate 和 Recreate 的区别？

**A**:
- **RollingUpdate**：逐步替换，保证服务可用（推荐）
- **Recreate**：先杀掉所有 Pod，再创建新的（有停机时间）

### Q3: Flannel VXLAN 的工作原理？

**A**: VXLAN 将内层以太网帧封装在 UDP 包中，通过 Overlay 网络传输。每个 Pod 有独立 IP，跨节点通信通过 VXLAN Tunnel 转发。

---

## 第五部分：生产实践

### 1. 调度器调优

```
调度器调优要点：
1. 自定义调度器：针对特殊 workload
2. PriorityClass：高优先级 Pod 抢占
3. Taint/Toleration：节点亲和性
4. Affinity：节点/Pod 亲和性
```

### 2. 控制器调优

```
控制器调优要点：
1. 调整 resyncPeriod（默认 12h）
2. 调整 concurrent-deployment-syncs
3. 监控 controller manager 延迟
```

### 3. 网络调优

```
网络调优要点：
1. MTU 设置（VXLAN 需要 1450）
2. CNI 插件选择（Calico > Flannel > Weave）
3. NetworkPolicy 控制
4. DNS 性能优化
```
