# GitOps工作流 - 资深专家深度实现

## 一、GitOps架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GitOps工作流                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Developer                                                             │
│        │                                                                │
│        ▼                                                                │
│   ┌─────────┐      Push      ┌─────────┐      Reconcile      ┌───────┐│
│   │  Code   │ ───────────►   │  Git    │ ────────────────►   │ K8s   ││
│   │  Repo   │                │  Repo   │                     │ Cluster││
│   └─────────┘                └─────────┘                     └───────┘│
│                                       ▲                                  │
│                                       │                                │
│                              ┌────────┴────────┐                       │
│                              │   ArgoCD/Flux  │                       │
│                              │   (Op Controller)│                      │
│                              └─────────────────┘                       │
│                                                                         │
│   核心原则:                                                              │
│   • 声明式配置                                                          │
│   • Git作为唯一真相源                                                    │
│   • 自动同步                                                            │
│   • 版本控制                                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、ArgoCD配置

```yaml
# argocd-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/k8s-manifests.git
    targetRevision: main
    path: overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

## 三、Pipeline设计

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

test:
  stage: test
  script:
    - docker run $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA tests

deploy:
  stage: deploy
  script:
    - argocd app sync my-app
  only:
    - main
```

## 四、面试高频题

### Q1: GitOps是什么？

```
A:
• 用Git管理基础设施配置
• 自动同步集群状态
• 版本控制和审计
```

### Q2: 如何实现自动部署？

```
A:
1. ArgoCD监听Git变化
2. 自动拉取最新配置
3. 同步到K8s集群
```

## 五、自测题

1. 解释GitOps核心原则
2. 如何配置自动同步？
3. 如何处理配置漂移？

---

## 参考文档

- [ArgoCD文档](https://argo-cd.readthedocs.io/)
- [GitOps规范](https://www.gitops.tech/)
