# K8s生产排障实战 - 资深专家深度实现

## 一、排查框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    K8s 生产排障流程                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Step 1: 定位问题                          Step 3: 修复验证              │
│   ┌──────────────┐                        ┌──────────────┐            │
│   │ 症状收集      │                        │  热修复       │            │
│   │ 影响范围评估  │                        │  回滚预案     │            │
│   └──────┬───────┘                        └──────┬───────┘            │
│          ▼                                       ▼                     │
│   Step 2: 根因分析                          Step 4: 复盘总结            │
│   ┌──────────────┐                        ┌──────────────┐            │
│   │ 日志分析      │                        │  知识库更新   │            │
│   │ 指标关联      │                        │  预防措施     │            │
│   │ 事件追踪      │                        └──────────────┘            │
│   └──────────────┘                                                         │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、常见问题排查

```bash
# Pod状态异常
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous

# 节点问题
kubectl describe node <node-name>
kubectl get events -A --field-selector involvedObject.name=<node-name>

# 网络问题
kubectl exec -it <pod-name> -- nslookup <service>
kubectl port-forward <pod-name> 8080:80

# 资源不足
kubectl top pod -n <namespace>
kubectl top node
```

## 三、内存溢出排查

```yaml
# OOMKill诊断
apiVersion: v1
kind: Pod
metadata:
  name: oom-test
spec:
  containers:
  - name: app
    image: myapp:latest
    resources:
      requests:
        memory: "128Mi"
        cpu: "250m"
      limits:
        memory: "256Mi"    # 设置limit触发OOM
        cpu: "500m"
```

```bash
# 查看OOM日志
kubectl get events -n default | grep -i oom
kubectl describe pod <pod-name> | grep -A5 "Last State"

# 内存泄漏检测
kubectl exec -it <pod-name> -- cat /sys/fs/cgroup/memory/memory.usage_in_bytes
```

## 四、面试高频题

### Q1: 如何排查Pod启动失败？

```
A:
1. kubectl describe pod
2. 查看Events
3. 检查镜像拉取
4. 验证资源配置
```

### Q2: 如何处理节点NotReady？

```
A:
1. 检查kubelet状态
2. 查看节点事件
3. 检查资源占用
4. 重启kubelet
```

## 五、自测题

1. 解释排查框架
2. 如何排查OOM？
3. 如何处理NotReady？

---

## 参考文档

- [K8s Troubleshooting](https://kubernetes.io/docs/tasks/debug/)
- [Kubectl Reference](https://kubernetes.io/docs/reference/kubectl/)
