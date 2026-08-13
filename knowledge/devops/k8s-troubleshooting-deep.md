# Kubernetes生产排障实战 - 资深专家深度实现

## 一、常见问题分类

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      K8s故障分类                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Pod层面                                                              │
│     • CrashLoopBackOff (容器反复崩溃)                                     │
│     • ImagePullBackOff (镜像拉取失败)                                     │
│     • Pending (调度失败)                                                 │
│     • ContainerCreating (启动缓慢)                                       │
│                                                                         │
│  2. Service层面                                                          │
│     • Endpoint不存在                                                     │
│     • 端口映射错误                                                       │
│     • DNS解析失败                                                        │
│                                                                         │
│  3. 资源层面                                                             │
│     • OOMKilled (内存溢出)                                               │
│     • CPU throttling (CPU限流)                                           │
│     • DiskPressure (磁盘压力)                                            │
│     • MemoryPressure (内存压力)                                          │
│                                                                         │
│  4. 网络层面                                                             │
│     • CNI插件故障                                                        │
│     • iptables规则冲突                                                   │
│     • DNS服务不可用                                                      │
│                                                                         │
│  5. 控制平面                                                             │
│     • API Server无响应                                                   │
│     • etcd性能瓶颈                                                       │
│     • Controller Manager异常                                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Pod故障排查

### 2.1 CrashLoopBackOff

```bash
# 1. 查看Pod状态
kubectl get pods -A | grep CrashLoopBackOff

# 2. 查看事件
kubectl describe pod <pod-name> -n <namespace>

# 常见原因:
# • 应用启动失败 (代码bug)
# • 配置错误 (环境变量/ConfigMap)
# • 资源不足 (OOMKilled)
# • 健康检查失败

# 3. 查看日志
kubectl logs <pod-name> -n <namespace> --previous
kubectl logs -f <pod-name> -n <namespace>

# 4. 查看容器资源限制
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].resources}'

# 5. 检查是否OOM
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```

```go
// 典型OOM场景
package main

import (
    "flag"
    "os"
)

func main() {
    // 从环境变量读取配置
    memoryLimit := os.Getenv("MEMORY_LIMIT")
    if memoryLimit == "" {
        memoryLimit = "256Mi"
    }
    
    // 申请内存
    data := make([]byte, parseMemory(memoryLimit))
    
    // 使用内存...
    use(data)
}
```

### 2.2 ImagePullBackOff

```bash
# 1. 检查镜像名称和tag
kubectl describe pod <pod-name> | grep Image

# 2. 检查Secret（私有仓库）
kubectl get secret <secret-name> -n <namespace>

# 3. 手动测试拉取
docker pull <image-name>

# 常见原因:
# • 镜像不存在
# • 仓库权限不足
# • 网络问题
# • tag错误
```

```yaml
# 正确配置imagePullSecrets
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  imagePullSecrets:
  - name: registry-secret
  containers:
  - name: app
    image: registry.example.com/myapp:v1.0
```

### 2.3 Pending状态

```bash
# 1. 查看Pod事件
kubectl describe pod <pod-name>

# 常见原因:
# • 资源不足 (CPU/Memory)
# • NodeSelector不匹配
# • Taints未容忍
# • PVC无法绑定

# 2. 检查节点资源
kubectl top nodes

# 3. 检查PVC状态
kubectl get pvc -A

# 4. 检查节点标签和taint
kubectl get nodes --show-labels
kubectl taint nodes <node>
```

---

## 三、网络故障排查

### 3.1 DNS问题

```bash
kubectl run test-dns --image=busybox --restart=Never -it --rm -- nslookup kubernetes.default

kubectl get pods -n kube-system -l k8s-app=kube-dns

kubectl get configmap coredns -n kube-system -o yaml

kubectl logs -n kube-system -l k8s-app=kube-dns
```

```yaml
# CoreDNS配置示例
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
           lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
           ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

### 3.2 Service问题

```bash
kubectl get svc <svc-name> -n <namespace>
kubectl get endpoints <svc-name> -n <namespace>

kubectl get pods -n <namespace> -l app=myapp

kubectl run tmp-shell --rm -it --image=bash --namespace=<ns> -- bash
# 在Pod内测试
curl http://<svc-name>:<port>

iptables -t nat -L KUBE-SERVICES -n -v
```

### 3.3 Ingress问题

```bash
kubectl get pods -n ingress-nginx

kubectl get ingress -A

kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx

kubectl port-forward svc/ingress-nginx-controller 8080:80 -n ingress-nginx
curl http://localhost:8080/
```

---

## 四、资源问题排查

### 4.1 OOMKilled

```bash
# 1. 查看Pod内存使用
kubectl top pod <pod-name>

# 2. 查看容器历史OOM事件
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>

# 3. 分析内存使用
kubectl exec <pod-name> -- cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes
kubectl exec <pod-name> -- cat /sys/fs/cgroup/memory/memory.usage_in_bytes
```

```yaml
# 正确的资源限制配置
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:latest
    resources:
      requests:
        memory: "256Mi"
        cpu: "250m"
      limits:
        memory: "512Mi"
        cpu: "500m"
```

### 4.2 CPU Throttling

```bash
# 1. 查看CPU使用
kubectl top pod <pod-name>

# 2. 查看CPU throttling统计
kubectl exec <pod-name> -- cat /sys/fs/cgroup/cpu/cpu.stat

# 3. 分析CPU使用
kubectl top pod <pod-name> --containers

# 解决方法:
# • 增加CPU limit
# • 优化代码减少CPU使用
# • 使用HPA自动扩缩容
```

### 4.3 磁盘压力

```bash
# 1. 检查节点磁盘
kubectl get nodes -o wide
kubectl describe node <node-name> | grep -A 5 Conditions

# 2. 查看磁盘使用
ssh <node-ip>
df -h
du -sh /var/lib/containerd/*

# 3. 清理无用数据
crictl rmi --prune
crictl rm $(crictl ps -a -q)
```

---

## 五、控制平面故障

### 5.1 API Server问题

```bash
kubectl get nodes
kubectl get cs

kubectl logs -n kube-system kube-apiserver-<node>

ETCDCTL_API=3 etcdctl endpoint health \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key
```

### 5.2 etcd问题

```bash
ETCDCTL_API=3 etcdctl member list \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

ETCDCTL_API=3 etcdctl endpoint status \
  --endpoints=https://127.0.0.1:2379 \
  --write-out=table

# • etcd磁盘IO慢
# • etcd存储空间不足
# • etcd快照过大
```

### 5.3 Controller Manager问题

```bash
kubectl logs -n kube-system kube-controller-manager-<node>

# • Node Controller: 节点健康检查
# • ReplicaSet Controller: Pod副本管理
# • Deployment Controller: 滚动更新
# • Job Controller: Job执行
# • Endpoint Controller: Endpoint维护
```

---

## 六、诊断工具链

### 6.1 常用命令

```bash
#!/bin/bash
# k8s-diagnose.sh - Kubernetes诊断脚本

NAMESPACE="${1:-default}"
POD_NAME="${2:-}"

echo "=========================================="
echo "  Kubernetes 诊断报告"
echo "  时间: $(date)"
echo "=========================================="

# Pod状态
echo -e "\n【Pod状态】"
kubectl get pods -n $NAMESPACE -o wide

# Pod事件
echo -e "\n【最近事件】"
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -20

# 资源使用
echo -e "\n【资源使用】"
kubectl top pods -n $NAMESPACE 2>/dev/null || echo "metrics-server未安装"

# 节点状态
echo -e "\n【节点状态】"
kubectl get nodes

# 关键服务
echo -e "\n【关键服务状态】"
kubectl get pods -n kube-system | grep -E "coredns|kube-proxy|etcd|apiserver"

# 如果指定了Pod，显示详细信息
if [ -n "$POD_NAME" ]; then
    echo -e "\n【Pod详情】"
    kubectl describe pod $POD_NAME -n $NAMESPACE
    
    echo -e "\n【Pod日志】"
    kubectl logs $POD_NAME -n $NAMESPACE --tail=50
    
    echo -e "\n【Pod exec】"
    echo "请在以下shell中执行诊断命令:"
    kubectl exec -it $POD_NAME -n $NAMESPACE -- /bin/bash
fi
```

### 6.2 性能分析

```bash
# 1. 使用 kubectl-debug
kubectl debug node/<node-name> -it --image=agent-container

# 2. 使用 eBPF工具
kubectl exec -it bug-tool -- bpftrace -e '
    tracepoint:syscalls:sys_enter_read {
        printf("%s %d\n", comm, arglen);
    }
'

# 3. 网络诊断
kubectl exec -it <pod> -- nc -zv <service> <port>
kubectl exec -it <pod> -- tcpdump -i any port <port>
```

---

## 七、自测题

### 7.1 基础题
1. Pod处于Pending状态，可能的原因有哪些？
2. 如何查看Pod的详细事件？
3. Service无法访问，排查步骤是什么？

### 7.2 进阶题
1. 如何排查CoreDNS解析失败？
2. 如何分析Pod的CPU Throttling？
3. etcd性能下降的可能原因？

### 7.3 实战题
1. 线上Pod频繁重启，如何定位问题？
2. 服务间调用超时，如何排查网络问题？
3. 节点出现DiskPressure，如何处理？

---

## 参考文档

- [Kubernetes Troubleshooting](https://kubernetes.io/docs/tasks/debug/)
- [kubectl Reference](https://kubernetes.io/docs/reference/kubectl/)
- [Kubernetes Debugging](https://kubernetes.io/docs/tasks/debug/debug-application/)
