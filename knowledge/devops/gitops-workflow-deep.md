# GitOps工作流 - 资深专家深度实现

## 一、核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GitOps工作流                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Developer              Git Repo              ArgoCD                  Cluster                   │
│       │                    │                      │                      │                      │
│       │  commit            │                      │                      │                      │
│       ├───────────────────►│                      │                      │                      │
│       │                    │                      │                      │                      │
│       │                    │◄─────────────────────┤                      │                      │
│       │                    │      watch           │                      │                      │
│       │                    │                      │                      │                      │
│       │                    │                      │                      │                      │
│       │                    │◄─────────────────────┤                      │                      │
│       │                    │   reconcile          │                      │                      │
│       │                    │                      │                      │                      │
│       │                    │                      │                      │                      │
│       │                    │                      ├──────────────────────┼──────────────────────┤
│       │                    │                      │    apply manifests   │                      │
│       │                    │                      │                      │                      │
│                                                                         │                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、ArgoCD配置

```yaml
# application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: frontend
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/repo.git
    targetRevision: HEAD
    path: overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: frontend
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

## 三、Kustomize覆盖

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patchesStrategicMerge:
  - patch.yaml

images:
  - name: nginx
    newTag: "1.21"
```

## 四、面试高频题

### Q1: GitOps和CI/CD的区别？

```
A:
• GitOps: 声明式，Git是单一事实来源
• CI/CD: 过程式，注重构建部署流程
• GitOps更强调自动同步和漂移检测
```

### Q2: 如何实现自动回滚？

```
A:
1. ArgoCD自动修复 (selfHeal)
2. 版本回退 (git revert)
3. 蓝绿部署切换
```

## 五、自测题

1. 解释GitOps核心原则
2. 如何实现应用同步？
3. 如何处理配置漂移？

---

## 参考文档

- [ArgoCD官方文档](https://argo-cd.readthedocs.io/)
- [GitOps白皮书](https://www.gitops.tech/)
