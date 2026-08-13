# CI/CD流程优化 - 资深专家深度实现

## 一、Pipeline架构

### 1.1 多阶段流水线

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - docker build -t myapp:$CI_COMMIT_SHA .
  artifacts:
    paths:
      - build/

test:
  stage: test
  script:
    - go test ./...
  needs: [build]

deploy:
  stage: deploy
  script:
    - kubectl apply -f k8s/
  needs: [test]
```

### 1.2 并行构建

```yaml
parallel:
  matrix:
    - GOOS: [linux, darwin]
      GOARCH: [amd64, arm64]
  script:
    - GOOS=$GOOS GOARCH=$GOARCH go build -o bin/$GOOS_$GOARCH
```

## 二、缓存优化

### 2.1 Go模块缓存

```yaml
cache:
  key: "${CI_COMMIT_REF_SLUG}"
  paths:
    - ~/.cache/go-build
    - ~/go/pkg/mod

before_script:
  - export GOMODCACHE=$CI_PROJECT_DIR/.mod-cache
  - go mod download
```

### 2.2 Docker层缓存

```dockerfile
# 利用缓存层
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o app .
```

## 三、性能调优

### 3.1 构建加速

```yaml
variables:
  DOCKER_BUILDKIT: "1"
  BUILDKIT_PROGRESS: "plain"

build:
  stage: build
  script:
    - docker build --progress=plain --cache-from=cache:latest -t app:latest .
```

### 3.2 并行测试

```yaml
test:
  parallel: 4
  script:
    - go test -p 4 ./...
```

## 四、安全加固

```yaml
stages:
  - build
  - scan
  - deploy

security-scan:
  stage: scan
  script:
    - trivy image --severity HIGH,CRITICAL app:latest
    - grype app:latest
  allow_failure: true
```

## 五、面试高频题

### Q1: CI/CD的核心价值？

```
A: 自动化、快速反馈、持续交付
```

### Q2: 如何优化构建速度？

```
A:
1. 并行构建
2. 缓存依赖
3. 增量构建
```

## 六、自测题

1. 设计一个完整的CI/CD流水线
2. 如何实现构建缓存？

---

## 参考文档

- [GitLab CI文档](https://docs.gitlab.com/ee/ci/)
