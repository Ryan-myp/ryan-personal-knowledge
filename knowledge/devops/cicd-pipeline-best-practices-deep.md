# CI/CD 流水线最佳实践深度解析

> **领域**: DevOps / 持续集成
> **深度**: ⭐⭐⭐⭐⭐ 生产实践级
> **标签**: cicd, pipeline, gitlab, jenkins, github-actions
> **更新时间**: 2026-08-13
> **类型**: best-practices/devops

---

## 📌 核心流水线架构

### 1. 典型流水线阶段

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│  Source  │ → │  Build  │ → │  Test   │ → │ Deploy  │ → │ Monitor │
│  (Git)  │   │ (Compile)│   │(Unit+IT)│   │(Staging)│   │(Prometheus)│
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
     │             │             │             │             │
     ▼             ▼             ▼             ▼             ▼
  Webhook      Docker Image    Coverage      K8s Deploy    Alerts
  Trigger      Build Cache     Report        Blue/Green     Logs
```

### 2. GitLab CI 配置示例

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

variables:
  DOCKER_REGISTRY: registry.example.com
  APP_NAME: myapp

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA .
    - docker push $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
  artifacts:
    paths:
      - build/

test:
  stage: test
  image: $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
  script:
    - npm test
    - npm run coverage
  coverage: '/Coverage:.*?(\d+\.\d+%)/'

deploy:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl set image deployment/$APP_NAME app=$DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
  environment:
    name: staging
  only:
    - main
```

---

## 🔥 最佳实践清单

### 1. 快速反馈原则

```yaml
# 分层测试策略
test:
  stages:
    - unit          # 0-30s
    - integration   # 30-120s
    - e2e          # 2-10min
  
  unit_test:
    stage: unit
    script:
      - go test ./... -short -count=1
    timeout: 2m
    
  integration_test:
    stage: integration
    script:
      - docker-compose up -d
      - go test ./... -run Integration
    timeout: 5m
```

### 2.  artifact 管理

```yaml
# Artifact 策略
artifacts:
  paths:
    - build/
    - tests/reports/
    - coverage/
  expire_in: 1 week  # 自动清理
  
cache:
  paths:
    - node_modules/
    - ~/.cache/go-build
  key: "${CI_COMMIT_REF_SLUG}"
```

### 3. 安全扫描集成

```yaml
security_scan:
  stage: test
  image: security-scanner:latest
  script:
    - trivy image --severity HIGH,CRITICAL $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
    - sonar-scanner -Dsonar.projectKey=$APP_NAME
  allow_failure: false
```

---

## 💡 生产实战经验

### 1. 并行构建优化

```yaml
# 矩阵构建
matrix:
  inherit:
    variables:
      - BUILD_TYPE
  
  values:
    BUILD_TYPE: [linux-amd64, linux-arm64, darwin-amd64]
    
# 并行测试
test:
  parallel:
    matrix:
      - SHARD: [1, 2, 3, 4]
  script:
    - npm test -- --shard=$SHARD
```

### 2. 蓝绿部署策略

```yaml
deploy_production:
  stage: deploy
  script:
    - kubectl set image deployment/app-v2 app=$IMAGE
    - kubectl rollout status deployment/app-v2
    - kubectl scale deployment/app-v1 --replicas=0
    - kubectl scale deployment/app-v2 --replicas=3
  environment:
    name: production
```

---

## 📊 性能指标

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| 构建时间 | <2min | <5min | <10min |
| 测试时间 | <3min | <10min | <30min |
| 部署时间 | <1min | <5min | <10min |
| 失败率 | <1% | <5% | <10% |

---

## 🎓 面试高频问题

**Q: 如何优化 CI/CD 流水线速度？**
A: 四级优化：
1. 并行执行独立任务
2. 增量构建（仅编译变更文件）
3. 镜像缓存复用
4. 分布式构建节点

**Q: 如何处理流水线失败的重试？**
A: 三级策略：
1. 自动重试 2 次（指数退避）
2. 标记不稳定任务
3. 人工介入告警

---

## 📚 参考资源

- **GitLab CI**: https://docs.gitlab.com/ee/ci/
- **GitHub Actions**: https://docs.github.com/actions
- **Jenkins Pipeline**: https://www.jenkins.io/doc/pipeline/

---

*本解析从生产实践出发，提炼 CI/CD 最佳实践模式。*
