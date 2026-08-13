# CI/CD 流水线专家级深度实现

## 一、流水线设计原则

### 1.1 核心原则

```go
// CI/CD 流水线配置
type PipelineConfig struct {
    Name           string         `yaml:"name"`
    Triggers       TriggerConfig  `yaml:"triggers"`
    Stages         []Stage        `yaml:"stages"`
    Environment    EnvConfig      `yaml:"environment"`
    Notifications  []Notification `yaml:"notifications"`
    QualityGates   []QualityGate  `yaml:"quality_gates"`
}

type TriggerConfig struct {
    Branches       []string `yaml:"branches"`
    Tags           []string `yaml:"tags"`
    Events         []string `yaml:"events"` // push, pull_request, merge_request
    Paths          []string `yaml:"paths"`
    Concurrency    int      `yaml:"concurrency"`
}

type Stage struct {
    Name       string       `yaml:"name"`
    Image      string       `yaml:"image"`
    Services   []string     `yaml:"services"`
    Script     []string     `yaml:"script"`
    Artifacts  ArtifactCfg  `yaml:"artifacts"`
    Cache      CacheConfig  `yaml:"cache"`
    Rules      RuleConfig   `yaml:"rules"`
    Timeout    int          `yaml:"timeout"`
}

type QualityGate struct {
    Type          string  `yaml:"type"` // sonarqube, coverage, security
    Threshold     float64 `yaml:"threshold"`
    FailOnError   bool    `yaml:"fail_on_error"`
}

// 配置示例
// pipeline:
//   name: main-pipeline
//   triggers:
//     branches: [main, develop, 'release/*']
//     tags: ['v*']
//   stages:
//     - lint
//     - test
//     - build
//     - deploy
```

### 1.2 多阶段流水线

```go
// 分阶段构建与部署
type StagePipeline struct {
    Develop    DevelopStage
    Staging    StagingStage
    Production ProductionStage
}

type DevelopStage struct {
    Artifacts   []string
    ParallelJobs []int
    Cleanup     bool
}

type StagingStage struct {
    Environment string
    Rollout     RolloutStrategy
}

type RolloutStrategy struct {
    Type        string // canary, blue-green, rolling
    Percentage  int
    StepSize    int
    PauseTime   time.Duration
}

type ProductionStage struct {
    Approval       bool
    Manual         bool
    AuditTrail     bool
    Compliance     ComplianceCheck
}

// GitLab CI 配置
// .gitlab-ci.yml
// stages:
//   - build
//   - test
//   - staging
//   - production

// build:
//   stage: build
//   script:
//     - docker build -t $IMAGE:$TAG .
//     - docker push $IMAGE:$TAG
//   artifacts:
//     paths:
//       - build/
//     expire_in: 1 hour

// test:
//   stage: test
//   script:
//     - go test ./... -coverprofile=coverage.out
//   artifacts:
//     reports:
//       coverage_report:
//         coverage_format: cobertura
//         path: coverage.out

// staging:
//   stage: staging
//   script:
//     - kubectl apply -f k8s/staging/
//   environment:
//     name: staging

// production:
//   stage: production
//   script:
//     - kubectl apply -f k8s/production/
//   environment:
//     name: production
//   when: manual
```

## 二、容器化构建优化

### 2.1 多阶段构建

```dockerfile
# 第一阶段：依赖安装
FROM golang:1.21-alpine AS deps
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# 第二阶段：构建
FROM deps AS builder
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/bin/server .

# 第三阶段：运行时
FROM alpine:3.18
RUN apk add --no-cache ca-certificates tzdata
ENV TZ=Asia/Shanghai
COPY --from=builder /app/bin/server /usr/local/bin/server
EXPOSE 8080
USER nobody
ENTRYPOINT ["server"]
```

### 2.2 构建缓存策略

```yaml
# GitHub Actions 缓存配置
name: CI Pipeline
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Cache Go modules
        uses: actions/cache@v3
        with:
          path: ~/go/pkg/mod
          key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
          restore-keys: |
            ${{ runner.os }}-go-
      
      - name: Cache build artifacts
        uses: actions/cache@v3
        with:
          path: ~/.cache/go-build
          key: ${{ runner.os }}-go-build-${{ hashFiles('**/go.mod') }}
      
      - name: Build
        run: go build -o bin/server ./cmd/server

  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Run tests
        run: go test -race -coverprofile=coverage.txt -covermode=atomic ./...
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## 三、测试策略

### 3.1 分层测试

```go
// 测试金字塔
type TestPyramid struct {
    UnitTests      UnitTestConfig
    Integration    IntegrationTestConfig
    E2E            E2ETestConfig
}

type UnitTestConfig struct {
    CoverageThreshold float64 // 80%
    RaceDetector      bool
    Parallel          bool
}

type IntegrationTestConfig struct {
    Database     bool
    Cache        bool
    MessageQueue bool
}

type E2ETestConfig struct {
    Browser    string
    Timeout    int
    Parallel   int
}

// 测试执行配置
// .github/workflows/test.yml
// strategy:
//   matrix:
//     go: ['1.20', '1.21']
//     os: [ubuntu-latest]

// test:
//   runs-on: ${{ matrix.os }}
//   steps:
//     - name: Run unit tests
//       run: go test ./... -race -count=1
      
//     - name: Run integration tests
//       run: docker-compose up -d && go test ./internal/...
```

### 3.2 代码覆盖率

```go
// 覆盖率分析工具
type CoverageAnalyzer struct {
    Threshold float64
    Ignore    []string
}

func (a *CoverageAnalyzer) Analyze() (*CoverageReport, error) {
    // 执行测试并收集覆盖率
    cmd := exec.Command("go", "test", "./...", 
        "-coverprofile=coverage.out",
        "-covermode=count")
    
    report := &CoverageReport{}
    // 解析覆盖率数据
    return report, nil
}

type CoverageReport struct {
    PackageCoverage map[string]float64
    TotalCoverage   float64
    Functions       []FunctionCoverage
}
```

## 四、部署策略

### 4.1 蓝绿部署

```go
// 蓝绿部署实现
type BlueGreenDeployer struct {
    Current string // "blue" or "green"
    Switch  func() error
}

func (d *BlueGreenDeployer) Deploy() error {
    // 1. 部署新版本到非活动环境
    target := map[string]string{"blue": "green", "green": "blue"}[d.Current]
    err := d.deployTo(target)
    if err != nil {
        return err
    }
    
    // 2. 健康检查
    if !d.healthCheck(target) {
        return fmt.Errorf("health check failed for %s", target)
    }
    
    // 3. 切换流量
    err = d.switchTraffic(target)
    if err != nil {
        return err
    }
    
    d.Current = target
    return nil
}

// Kubernetes 蓝绿配置
// apiVersion: apps/v1
// kind: Deployment
// metadata:
//   name: myapp-blue
//   labels:
//     app: myapp
//     track: blue
// ---
// apiVersion: v1
// kind: Service
// metadata:
//   name: myapp
// spec:
//   selector:
//     app: myapp
//     track: blue  # 切换到 green 进行蓝绿部署
```

### 4.2 金丝雀发布

```go
// 金丝雀发布
type CanaryDeployer struct {
    CanaryPercent int
    StepSize      int
    PauseTime     time.Duration
}

func (d *CanaryDeployer) Deploy() error {
    // 逐步放量
    for percent := d.CanaryPercent; percent <= 100; percent += d.StepSize {
        err := d.setTraffic(percent)
        if err != nil {
            return err
        }
        
        // 监控指标
        metrics := d.monitorMetrics()
        if !d.isHealthy(metrics) {
            return d.rollback()
        }
        
        time.Sleep(d.PauseTime)
    }
    return nil
}
```

## 五、安全策略

### 5.1 镜像扫描

```yaml
# Trivy 镜像扫描
name: Security Scan
on: [push]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'myapp:latest'
          format: 'table'
          exit-code: '1'
          severity: 'CRITICAL,HIGH'
```

### 5.2 Secret 管理

```go
// Secret 管理规范
type SecretManager struct {
    Provider string // vault, aws-secrets-manager, k8s-secrets
}

func (m *SecretManager) Get(name string) (string, error) {
    switch m.Provider {
    case "vault":
        return m.getFromVault(name)
    case "aws-secrets-manager":
        return m.getFromAWS(name)
    default:
        return "", fmt.Errorf("unsupported provider")
    }
}

// CI/CD Secret 配置
// 禁止在代码中硬编码 Secret
// 使用环境变量或 Secret Manager
env:
  DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
  API_KEY: ${{ secrets.API_KEY }}
```

## 六、面试高频题

### Q1: 如何设计高效的CI/CD流水线？

```
A:
1. 并行化测试和构建
2. 使用增量构建
3. 缓存依赖和中间产物
4. 快速失败策略
5. 分层测试（单元测试→集成测试→E2E）
```

### Q2: 蓝绿部署 vs 金丝雀发布如何选择？

```
A:
1. 蓝绿部署：快速切换，回滚简单，资源加倍
2. 金丝雀发布：渐进式放量，风险可控，需要监控
3. 选择依据：业务连续性要求、用户规模、风险容忍度
```

### Q3: 如何保证CI/CD的安全性？

```
A:
1. 最小权限原则
2. Secret集中管理
3. 镜像签名和扫描
4. 审计日志
5. 安全策略自动化
```

## 七、自测题

1. 解释CI/CD流水线的分层设计
2. 如何实现零停机部署？
3. 如何优化构建速度？

---

## 参考文档

- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kaniko Build](https://kaniko.dev/)
