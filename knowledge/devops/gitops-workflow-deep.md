# GitOps 工作流深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、GitOps 核心概念

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GitOps 工作原理                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐      │
│  │   Git    │ ────▶ │  ArgoCD  │ ────▶ │  K8s     │ ────▶ │ Operator │      │
│  │  (Source)│      │(Controller)│      │(Cluster) │      │(Sync)   │      │
│  └──────────┘      └──────────┘      └──────────┘      └──────────┘      │
│       ▲                                                         │          │
│       └──────────────────  Self-healing ────────────────────────┘          │
│                                                                             │
│  核心原则:                                                                  │
│  ├── Git 作为唯一事实来源                                                   │
│  ├── 自动化部署 (无手动 kubectl)                                            │
│  ├── 持续协调 (Reconciliation Loop)                                         │
│  └── 声明式配置 (Declarative)                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、ArgoCD 架构

```yaml
# 文件: argocd/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ad-bidding-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/Ryan-myp/ad-platform.git
    targetRevision: main
    path: deployments/k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: advertising
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PruneLast=false
```

---

## 三、参考资料

```
核心项目:
├── ArgoCD: https://argo-cd.readthedocs.io/
├── Flux: https://fluxcd.io/
└── Helm: https://helm.sh/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
