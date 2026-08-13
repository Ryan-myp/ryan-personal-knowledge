# CI/CD 流水线优化 - 资深专家深度实现

## 一、流水线架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CI/CD 流水线架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Source → Build → Test → Scan → Deploy → Monitor                        │
│     │        │       │       │        │         │                       │
│     ▼        ▼       ▼       ▼        ▼         ▼                       │
│   Git    Docker    Unit   Security  K8s     Prometheus                  │
│          Build     Test    Scan     Apply    Monitoring                 │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、GitLab CI配置

```yaml
stages:
  - build
  - test
  - security
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  APP_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA

# 构建阶段
build:
  stage: build
  script:
    - docker build -t $APP_IMAGE .
    - docker push $APP_IMAGE
  only:
    - main

# 测试阶段
test:
  stage: test
  script:
    - docker run --rm $APP_IMAGE go test ./...
  needs: ["build"]

# 安全扫描
security-scan:
  stage: security
  script:
    - trivy image $APP_IMAGE
    - grype $APP_IMAGE
  needs: ["build"]

# 部署阶段
deploy:
  stage: deploy
  script:
    - kubectl set image deployment/app app=$APP_IMAGE
    - kubectl rollout status deployment/app
  needs: ["build", "test", "security"]
  only:
    - main
```

## 三、面试高频题

### Q1: 如何优化构建速度？

```
A:
1. 并行执行
2. 缓存依赖
3. 多阶段构建
```

### Q2: 如何实现安全扫描？

```
A:
1. SAST静态分析
2. DAST动态测试
3. 依赖漏洞扫描
```

## 四、自测题

1. 解释CI/CD流程
2. 如何优化构建？
3. 如何实现安全扫描？

---

## 参考文档

- [GitLab CI](https://docs.gitlab.com/ee/ci/)
- [Tekton](https://tekton.dev/)
