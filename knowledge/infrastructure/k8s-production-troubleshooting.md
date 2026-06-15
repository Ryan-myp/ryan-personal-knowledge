# K8s 生产排障实战

> Pod OOM/Pod Crash/网络问题/调度失败/资源不足

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台 K8s 常见问题

| 问题 | 现象 | 根因 |
|------|------|------|
| Pod OOM | CrashLoopBackOff | 内存超限 |
| Pod Crash | Error 状态 | 代码 Bug |
| 网络不通 | Connection refused | 网络策略/Service 配置 |
| 调度失败 | Pending | 资源不足 |
| 性能下降 | Latency 升高 | 资源争抢 |

---

## 第二部分：Pod OOM 排查

### 2.1 OOM 监控

```bash
# 查看 Pod 内存使用
kubectl top pods -n advertising

# 查看事件
kubectl get events -n advertising --sort-by='.lastTimestamp'

# 查看 Pod 状态
kubectl describe pod <pod-name> -n advertising

# 关键字段
# OOMKilled: 是否被 OOM Killer 终止
# Restart Count: 重启次数

# 查看容器日志
kubectl logs <pod-name> -n advertising --previous

# 查看资源限制
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].resources}'
```

### 2.2 OOM 优化

```yaml
# 合理的资源限制
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bidding-service
  namespace: advertising
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bidding-service
  template:
    metadata:
      labels:
        app: bidding-service
    spec:
      containers:
      - name: server
        image: registry.example.com/bidding-service:v1.2.3
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 2.3 Go 内存优化

```go
package main

import (
    "runtime"
    "sync"
)

func init() {
    // 设置 GOGC 控制 GC 频率
    runtime.GOMAXPROCS(runtime.NumCPU())
    
    // 优化内存分配
    runtime.SetGCPercent(20)  // 默认 100，降低触发 GC 的频率
    
    // 预分配切片
    slice := make([]int, 0, 10000)  // 预分配容量
}

// 使用 sync.Pool 减少内存分配
var bufPool = sync.Pool{
    New: func() interface{} {
        buf := make([]byte, 1024)
        return &buf
    },
}

func getBuf() *[]byte {
    return bufPool.Get().(*[]byte)
}

func putBuf(buf *[]byte) {
    *buf = (*buf)[:0]
    bufPool.Put(buf)
}
```

---

## 第三部分：Pod Crash 排查

### 3.1 Crash 原因分析

```bash
# 查看 Pod 状态
kubectl get pods -n advertising

# 查看 Pod 详细信息
kubectl describe pod <pod-name> -n advertising

# 关键字段:
# State: Waiting (CrashLoopBackOff)
# Last State: Terminated (Exit Code 137 = OOMKilled)

# 查看日志
kubectl logs <pod-name> -n advertising --tail=100

# 查看之前崩溃的日志
kubectl logs <pod-name> -n advertising --previous

# 查看事件
kubectl get events -n advertising --field-selector involvedObject.name=<pod-name>
```

### 3.2 常见 Crash 原因

```
Exit Code 137: OOMKilled
Exit Code 1: 应用错误
Exit Code 139: Segmentation Fault
Exit Code 143: SIGTERM (优雅退出)

排查步骤:
1. 查看日志: kubectl logs
2. 查看事件: kubectl describe pod
3. 检查资源: kubectl top pods
4. 检查配置: kubectl get deployment -o yaml
5. 调试: kubectl exec -it <pod> -- /bin/sh
```

---

## 第四部分：网络问题排查

### 4.1 网络诊断

```bash
# 查看 Service 端点
kubectl get endpoints <service-name> -n advertising

# 查看网络策略
kubectl get networkpolicy -n advertising

# 测试 Pod 间连通性
kubectl run test -it --rm --image=busybox --restart=Never -- /bin/sh

# 查看 DNS 解析
kubectl run test -it --rm --image=busybox --restart=Never -- nslookup <service-name>

# 查看 Pod 网络
kubectl get pods -o wide -n advertising

# 查看 CNI 插件状态
kubectl get pods -n kube-system | grep calico
kubectl get pods -n kube-system | weave
```

### 4.2 常见网络问题

```
问题1: Service 无法访问
原因: Endpoint 为空
解决: 检查 Selector 匹配

问题2: Pod 间无法通信
原因: NetworkPolicy 限制
解决: 检查 NetworkPolicy 规则

问题3: DNS 解析失败
原因: CoreDNS 故障
解决: 检查 CoreDNS Pod 状态

问题4: 外部无法访问
原因: Ingress/NodePort 配置
解决: 检查 Ingress 规则
```

---

## 第五部分：自测题

### 问题 1
Pod OOM 怎么排查？

<details>
<summary>查看答案</summary>

1. kubectl describe pod 查看 OOMKilled
2. kubectl logs --previous 查看崩溃前日志
3. kubectl top pods 监控内存使用
4. 调整 resources.limits.memory
5. Go 代码优化内存使用

</details>

### 问题 2
Pod CrashLoopBackOff 怎么解决？

<details>
<summary>查看答案</summary>

1. kubectl describe pod 查看 Exit Code
2. kubectl logs 查看应用日志
3. 检查配置是否正确
4. 检查依赖服务是否可用
5. 增加 liveness/readiness probe

</details>

### 问题 3
K8s 网络不通怎么排查？

<details>
<summary>查看答案</summary>

1. 检查 Service Endpoint
2. 检查 NetworkPolicy
3. 检查 CoreDNS
4. 测试 Pod 间连通性
5. 查看 CNI 插件状态

</details>

---

*本文档基于 K8s 生产排障经验整理。*