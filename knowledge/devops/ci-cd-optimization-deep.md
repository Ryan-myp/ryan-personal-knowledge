# CI/CD Pipeline优化 - 资深专家深度实现

## 一、Pipeline架构

```
┌─────────────────────────────────────────────────────────────┐
│                    CI/CD Pipeline                           │
│                                                             │
│  Source → Build → Test → Security → Staging → Production   │
│    ↑        ↑       ↑         ↑          ↑           ↑      │
│    │        │       │         │          │           │      │
│  Git     Docker   Jest      SAST       K8s        Monitor  │
│  webhook  build   E2E      SonarQube  Deploy     Alerting  │
└─────────────────────────────────────────────────────────────┘
```

## 二、GitLab CI配置

```yaml
stages:
  - build
  - test
  - security
  - deploy

variables:
  DOCKER_REGISTRY: registry.example.com
  APP_NAME: my-service

build:
  stage: build
  image: docker:24.0
  services:
    - docker:24.0-dind
  script:
    - docker build -t $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHORT_SHA .
    - docker push $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHORT_SHA
  only:
    - main
    - tags
```

## 三、Go构建优化

```dockerfile
# 多阶段构建
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/server /server
EXPOSE 8080
CMD ["/server"]
```

## 四、性能优化

| 优化项 | 方案 | 提升 |
|--------|------|------|
| 缓存 | Go模块缓存、Docker层缓存 | 40% |
| 并行 | 多阶段并行执行 | 50% |
| 增量 | 变更文件检测 | 60% |
| 构建 | 远端构建(BuildKit) | 30% |

## 五、面试高频题

### Q1: 如何优化CI/CD流水线？

```
A:
1. 并行化测试和执行
2. 使用增量构建
3. 缓存依赖和中间产物
4. 采用容器化构建环境
```

### Q2: 如何实现蓝绿部署？

```
A: 使用Kubernetes的Deployment滚动更新+Service流量切换。
```

## 六、自测题

1. 设计一个完整的CI/CD流水线
2. 如何实现零停机部署？

---

## 参考文档

- [GitLab CI文档](https://docs.gitlab.com/ee/ci/)
