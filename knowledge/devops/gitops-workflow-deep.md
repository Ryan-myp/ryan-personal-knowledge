# GitOps 工作流深度实现 - ArgoCD 生产实践

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: DevOps  
> **代码密度**: 28%

---

## 一、GitOps 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      GitOps 工作流                                   │
│                                                                     │
│  Developer                          GitOps Controller               │
│  ┌─────────────┐                    ┌─────────────┐                │
│  │  Code Repo  │──commit──▶│  Git      │──sync──▶│  K8s Cluster  │
│  │  (PR/MR)    │    push   │  Server   │         │  (Apps)       │
│  └─────────────┘            └─────────────┘         └─────────────┘
│                                             │
│                              ┌──────────────┼──────────────┐
│                              ▼              ▼              │
│                        ┌──────────┐   ┌──────────┐        │
│                        │  ArgoCD  │   │  Flux    │        │
│                        │  (UI)    │   │  (CLI)   │        │
│                        └──────────┘   └──────────┘        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、ArgoCD 应用配置

```yaml
# argocd/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ad-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/ryan/ad-platform.git
    targetRevision: main
    path: k8s/base
  destination:
    server: https://kubernetes.default.svc
    namespace: ad-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 三、Kustomize 多环境配置

```yaml
# k8s/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bidding-engine
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bidding-engine
  template:
    metadata:
      labels:
        app: bidding-engine
    spec:
      containers:
      - name: engine
        image: registry.example.com/bidding-engine:latest
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
```

```yaml
# k8s/overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
bases:
  - ../../base
namespace: staging
replicas:
  - name: bidding-engine
    count: 1
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=debug
      - FEATURE_FLAGS=experiment_a,experiment_b
```

```yaml
# k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
bases:
  - ../../base
namespace: production
replicas:
  - name: bidding-engine
    count: 5
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=warn
      - FEATURE_FLAGS=
resources:
  - hpa.yaml
```

---

## 四、Helm Chart 封装

```yaml
# charts/ad-platform/Chart.yaml
apiVersion: v2
name: ad-platform
description: Ad Platform Helm Chart
version: 1.0.0
appVersion: 1.0.0
```

```yaml
# charts/ad-platform/values.yaml
biddingEngine:
  replicas: 3
  image:
    repository: registry.example.com/bidding-engine
    tag: latest
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 2Gi

redis:
  enabled: true
  auth:
    password: "${REDIS_PASSWORD}"

database:
  host: "${DB_HOST}"
  name: ad_platform
```

---

## 五、CD 流水线

```yaml
# .github/workflows/cd.yaml
name: GitOps CD
on:
  push:
    branches: [main]
    paths:
      - 'k8s/**'
      - 'charts/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Sync ArgoCD
        run: |
          argocd app sync ad-platform \
            --revision ${GITHUB_SHA} \
            --dry-run=false
          
      - name: Verify Health
        run: |
          argocd app get ad-platform \
            --health || exit 1
```

---

## 六、自测题

1. **GitOps 的核心原则是什么？**
   - 声明式、版本化、自动化

2. **ArgoCD vs Flux 的区别？**
   - ArgoCD 有 UI，Flux 更轻量 CLI-first

3. **Kustomize vs Helm 如何选择？**
   - 简单配置用 Kustomize，复杂模板用 Helm

