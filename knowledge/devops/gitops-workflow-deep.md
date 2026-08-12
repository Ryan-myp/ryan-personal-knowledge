# GitOps 工作流深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、GitOps 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GitOps 工作流架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  开发者 ──┐                                                                 │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │   GitHub/GitLab │ ← 代码仓库 (Git)                                       │
│  │   (Manifests)   │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           │ push event                                                     │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │   CI Pipeline   │ ← 构建 + 测试 + 推送镜像                              │
│  │   (GitHub       │                                                        │
│  │    Actions)     │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           │ image push                                                      │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │   ArgoCD        │ ← GitOps 控制器 (持续同步)                            │
│  │   (K8s 上运行)  │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │   Kubernetes    │ ← 目标集群                                            │
│  │   (生产环境)    │                                                        │
│  └─────────────────┘                                                        │
│                                                                             │
│  核心原则:                                                                   │
│  • 单一事实来源: Git                                                        │
│  • 声明式配置                                                                │
│  • 自动同步                                                                  │
│  • 审计追踪                                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、ArgoCD Application 配置

```yaml
# 文件: argocd/apps/ad-bidding.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ad-bidding-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/ryan-myp/ad-platform-infrastructure.git
    targetRevision: main
    path: k8s/ad-bidding
    
  destination:
    server: https://kubernetes.default.svc
    namespace: advertising
    
  syncPolicy:
    automated:
      prune: true           # 自动清理废弃资源
      selfHeal: true        # 自动修复漂移
      
    syncOptions:
      - CreateNamespace=true
      
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
```

---

## 三、Kustomize 环境管理

```yaml
# 文件: k8s/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ad-bidding
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: bidding
        image: ghcr.io/ryan-myp/ad-bidding:latest
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
```

```yaml
# 文件: k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: ghcr.io/ryan-myp/ad-bidding
    newTag: v1.5.0

patches:
  - path: deployment-patch.yaml
  
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
      - METRICS_ENABLED=true
```

```yaml
# 文件: k8s/overlays/production/deployment-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ad-bidding
spec:
  replicas: 10
  template:
    spec:
      containers:
      - name: bidding
        resources:
          requests:
            cpu: 1000m
            memory: 1Gi
          limits:
            cpu: 4000m
            memory: 4Gi
```

---

## 四、参考资料

```
核心工具:
├── ArgoCD: https://argoproj.github.io/cd/
├── Flux CD: https://fluxcd.io/
└── GitLab Runner: CI/CD 集成

最佳实践:
├── "GitOps: Operate Kubernetes at Scale" (Weaveworks)
└── CNCF GitOps Whitepaper
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
