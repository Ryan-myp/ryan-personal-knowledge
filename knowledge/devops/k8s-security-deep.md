# K8s安全加固 - 资深专家深度实现

## 一、安全分层

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    K8s安全分层架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Layer 1: 节点安全 (Node Security)                                       │
│   ├── 内核加固                                                            │
│   ├── 容器运行时安全                                                       │
│   └── 网络隔离                                                              │
│                                                                         →
│   Layer 2: 集群安全 (Cluster Security)                                     │
│   ├── RBAC权限控制                                                          │
│   ├── Pod安全策略                                                           │
│   └── 网络策略                                                              │
│                                                                         →
│   Layer 3: 应用安全 (Application Security)                                 │
│   ├── 镜像安全                                                              │
│   ├── 配置管理                                                              │
│   └── 密钥管理                                                              │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、RBAC配置

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
  
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: read-pods
subjects:
- kind: User
  name: developer
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

## 三、Pod安全策略

```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: restricted
spec:
  privileged: false
  allowPrivilegeEscalation: false
  runAsUser:
    rule: MustRunAsNonRoot
  fsGroup:
    rule: MustRunAs
    ranges:
    - min: 1
      max: 65535
  volumes:
  - 'configMap'
  - 'emptyDir'
  - 'projected'
```

## 四、面试高频题

### Q1: 如何保障K8s安全？

```
A:
1. 最小权限原则
2. 网络隔离
3. 镜像扫描
```

### Q2: RBAC如何工作？

```
A:
1. Role定义权限
2. RoleBinding绑定用户
3. 访问控制检查
```

## 五、自测题

1. 解释K8s安全分层
2. 如何实现RBAC？
3. 如何保障安全？

---

## 参考文档

- [K8s Security](https://kubernetes.io/docs/concepts/security/)
- [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
