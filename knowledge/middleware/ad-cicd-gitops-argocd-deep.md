# CI/CD 深度：GitOps/ArgoCD/流水线源码级

> 从 Jenkinsfile 到 ArgoCD，逐行解析现代 CI/CD 流水线

---

## 第一部分：GitOps 架构

```
GitOps 工作流程：
┌─────────────────────────────────────────────────────────────────────┐
│ Developer                                                            │
│ ├── 修改代码 → git push → PR                                         │
│ ├── CI 触发：build/test/lint                                        │
│ ├── PR 合并 → main 分支                                             │
│ └── 更新 Helm Chart / Kustomize                                      │
│                                                                      │
│ Git Repository (Source of Truth)                                     │
│ ├── manifests/                                                       │
│ │   ├── base/                                                        │
│ │   └── overlays/                                                    │
│ ├── helm-charts/                                                     │
│ └── kustomization.yaml                                               │
│                                                                      │
│ ArgoCD                                                               │
│ ├── 监听 Git 变更                                                    │
│ ├── 对比 Git vs K8s 状态                                             │
│ ├── 自动同步（Auto-Sync）                                            │
│ └── 漂移检测（Drift Detection）                                       │
│                                                                      │
│ Kubernetes Cluster                                                   │
│ ├── Namespace: production                                            │
│ ├── Deployment: ad-platform                                          │
│ ├── Service: ad-platform                                             │
│ └── Ingress: ad-platform                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：Jenkins Pipeline 源码

```groovy
// Jenkinsfile：广告平台 CI/CD 流水线
pipeline {
    agent {
        kubernetes {
            yaml """
            apiVersion: v1
            kind: Pod
            spec:
              containers:
              - name: golang
                image: golang:1.21-alpine
                volumeMounts:
                - name: docker-sock
                  mountPath: /var/run/docker.sock
              volumes:
              - name: docker-sock
                hostPath:
                  path: /var/run/docker.sock
            """
        }
    }
    
    environment {
        REGISTRY = 'registry.cn-hangzhou.aliyuncs.com'
        IMAGE_NAME = 'ad-platform'
        VERSION = "${env.BUILD_NUMBER}"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Lint') {
            steps {
                sh '''
                go vet ./...
                golangci-lint run ./...
                '''
            }
        }
        
        stage('Test') {
            steps {
                sh '''
                go test -race -coverprofile=coverage.out ./...
                go tool cover -func=coverage.out
                '''
            }
            post {
                success {
                    cobertura coveragePattern: 'coverage.out'
                }
            }
        }
        
        stage('Build') {
            steps {
                script {
                    // 1. 构建镜像
                    sh """
                    docker build -t ${REGISTRY}/${IMAGE_NAME}:${VERSION} .
                    docker tag ${REGISTRY}/${IMAGE_NAME}:${VERSION} \\
                        ${REGISTRY}/${IMAGE_NAME}:latest
                    """
                    
                    // 2. 推送镜像
                    sh """
                    docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}
                    docker push ${REGISTRY}/${IMAGE_NAME}:latest
                    """
                }
            }
        }
        
        stage('Security Scan') {
            steps {
                sh '''
                trivy image ${REGISTRY}/${IMAGE_NAME}:${VERSION}
                '''
            }
        }
        
        stage('Deploy to Staging') {
            steps {
                script {
                    // 1. 更新 Helm values
                    sh """
                    helm upgrade --install ad-platform \\
                        ./charts/ad-platform \\
                        --namespace staging \\
                        --set image.tag=${VERSION} \\
                        --set image.registry=${REGISTRY} \\
                        --wait --timeout 300s
                    """
                }
            }
        }
        
        stage('Integration Test') {
            steps {
                sh '''
                ./scripts/integration-test.sh
                '''
            }
        }
        
        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            steps {
                script {
                    // 1. 灰度发布（先 10%）
                    sh """
                    kubectl set image deployment/ad-platform \\
                        ad-platform=${REGISTRY}/${IMAGE_NAME}:${VERSION} \\
                        -n production
                    """
                    
                    // 2. 等待健康检查
                    sh '''
                    sleep 60
                    kubectl rollout status deployment/ad-platform \\
                        -n production --timeout=300s
                    '''
                    
                    // 3. 全量发布
                    sh '''
                    kubectl rollout restart deployment/ad-platform \\
                        -n production
                    '''
                }
            }
        }
    }
    
    post {
        always {
            // 清理工作空间
            cleanWs()
        }
        failure {
            // 发送通知
            slackSend(
                channel: '#dev-alerts',
                message: "❌ Build failed: ${env.BUILD_URL}"
            )
        }
        success {
            slackSend(
                channel: '#dev-alerts',
                message: "✅ Build succeeded: ${env.BUILD_URL}"
            )
        }
    }
}
```

---

## 第三部分：ArgoCD 源码

```yaml
# ArgoCD Application：广告平台
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ad-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/ryan-myp/ad-platform-manifests.git
    targetRevision: main
    path: overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true  # 自动删除 Git 中不存在的资源
      selfHeal: true  # 自动修复漂移
    syncOptions:
      - CreateNamespace=true
      - PruneLast=true
  revisionHistoryLimit: 10
```

```yaml
# Kustomization：生产环境配置
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: production

resources:
  - ../../base

images:
  - name: ad-platform
    newName: registry.cn-hangzhou.aliyuncs.com/ad-platform
    newTag: "1.2.3"

patches:
  - path: replica-count.yaml
    target:
      kind: Deployment
      name: ad-platform

configMapGenerator:
  - name: ad-config
    literals:
      - AD_BUDGET_LIMIT=100000
      - ENABLE_DARK_MODE=true
```

```yaml
# base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ad-platform
  labels:
    app: ad-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ad-platform
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: ad-platform
    spec:
      containers:
        - name: ad-platform
          image: registry.cn-hangzhou.aliyuncs.com/ad-platform:latest
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 20
```

---

## 第四部分：自测题

### Q1: GitOps 和传统 CI/CD 的区别？

**A**: GitOps 以 Git 为唯一真相源，ArgoCD 自动同步 K8s 状态；传统 CI/CD 通过 Jenkins 直接操作 K8s。

### Q2: ArgoCD 的 Self-Heal 是什么？

**A**: 当 K8s 状态与 Git 不一致时，ArgoCD 自动修复到 Git 定义的状态。

### Q3: 灰度发布怎么实现？

**A**: 先更新 10% Pod，监控指标正常后再全量更新。

---

## 第五部分：生产实践

### 1. 流水线优化

```
流水线优化要点：
1. 并行执行
2. 缓存依赖
3. 增量构建
4. 分层镜像
```

### 2. 安全扫描

```
安全扫描要点：
1. 镜像漏洞扫描（Trivy）
2. 代码安全扫描（Semgrep）
3. 依赖漏洞检查（Dependabot）
4. 签名验证（Cosign）
```

### 3. 监控

```
监控要点：
1. 部署成功率
2. 部署时长
3. 回滚频率
4. 漂移检测
```

---

## Go 代码实战：CI/CD Pipeline 编排

### 1. Pipeline Runner（Pipeline 引擎）

```go
package pipeline

import (
	"context"
	"fmt"
	"os/exec"
	"sync"
	"time"
)

// Stage Pipeline阶段
type Stage struct {
	Name      string
	Jobs      []*Job
	Strategy  Strategy // parallel, serial
}

type Strategy int

const (
	Parallel Strategy = iota
	Serial
)

// Job Pipeline任务
type Job struct {
	Name     string
	Steps    []Step
	Timeout  time.Duration
	Retries  int
	OnFailure string // continue, abort
}

type Step func(ctx context.Context) error

// PipelineRunner Pipeline执行器
type PipelineRunner struct {
	stages []*Stage
	results map[string]*JobResult
	mu    sync.Mutex
}

type JobResult struct {
	JobName  string
	Status   string // success, failed, skipped
	Duration time.Duration
	Error    error
}

func NewPipelineRunner(stages ...*Stage) *PipelineRunner {
	return &PipelineRunner{
		stages:  stages,
		results: make(map[string]*JobResult),
	}
}

func (pr *PipelineRunner) Execute(ctx context.Context) error {
	for _, stage := range pr.stages {
		switch stage.Strategy {
		case Parallel:
			if err := pr.runParallel(ctx, stage); err != nil {
				return err
			}
		case Serial:
			if err := pr.runSerial(ctx, stage); err != nil {
				return err
			}
		}
	}
	return nil
}

func (pr *PipelineRunner) runParallel(ctx context.Context, stage *Stage) error {
	var wg sync.WaitGroup
	errCh := make(chan error, len(stage.Jobs))
	
	for _, job := range stage.Jobs {
		wg.Add(1)
		go func(j *Job) {
			defer wg.Done()
			
			jobCtx, cancel := context.WithTimeout(ctx, j.Timeout)
			defer cancel()
			
			for attempt := 0; attempt <= j.Retries; attempt++ {
				select {
				case <-jobCtx.Done():
					pr.recordResult(j.Name, "failed", 0, jobCtx.Err())
					errCh <- jobCtx.Err()
					return
				default:
				}
				
				start := time.Now()
				var lastErr error
				for _, step := range j.Steps {
					if err := step(jobCtx); err != nil {
						lastErr = err
						break
					}
				}
				
				duration := time.Since(start)
				if lastErr == nil {
					pr.recordResult(j.Name, "success", duration, nil)
					return
				}
				
				if attempt < j.Retries {
					time.Sleep(time.Duration(attempt+1) * time.Second) // 指数退避
					continue
				}
				
				pr.recordResult(j.Name, "failed", duration, lastErr)
				errCh <- lastErr
			}
		}(job)
	}
	
	wg.Wait()
	close(errCh)
	
	for err := range errCh {
		if err != nil {
			return err
		}
	}
	return nil
}

func (pr *PipelineRunner) runSerial(ctx context.Context, stage *Stage) error {
	for _, job := range stage.Jobs {
		jobCtx, cancel := context.WithTimeout(ctx, job.Timeout)
		result := &JobResult{}
		
		for attempt := 0; attempt <= job.Retries; attempt++ {
			start := time.Now()
			var lastErr error
			for _, step := range job.Steps {
				if err := step(jobCtx); err != nil {
					lastErr = err
					break
				}
			}
			result.Duration = time.Since(start)
			result.JobName = job.Name
			
			if lastErr == nil {
				result.Status = "success"
				break
			}
			
			if attempt < job.Retries {
				time.Sleep(time.Duration(attempt+1) * time.Second)
				continue
			}
			
			result.Status = "failed"
			result.Error = lastErr
		}
		
		pr.mu.Lock()
		pr.results[job.Name] = result
		pr.mu.Unlock()
		
		if result.Status == "failed" {
			return fmt.Errorf("job %s failed: %w", job.Name, result.Error)
		}
		cancel()
	}
	return nil
}

func (pr *PipelineRunner) recordResult(name, status string, dur time.Duration, err error) {
	pr.mu.Lock()
	defer pr.mu.Unlock()
	pr.results[name] = &JobResult{
		JobName:  name,
		Status:   status,
		Duration: dur,
		Error:    err,
	}
}
```

### 2. ArgoCD Sync 控制器

```go
package argocd

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"time"
)

// AppStatus 应用状态
type AppStatus struct {
	Phase       string `json:"phase"`
	Message     string `json:"message"`
	Health      string `json:"health"`
	Resources   []ResourceStatus `json:"resources"`
}

type ResourceStatus struct {
	Kind      string `json:"kind"`
	Namespace string `json:"namespace"`
	Name      string `json:"name"`
	Status    string `json:"status"`
	Health    string `json:"health"`
}

// SyncController ArgoCD同步控制器
type SyncController struct {
	argocdURL  string
	token      string
	namespace  string
	interval   time.Duration
}

func NewSyncController(url, token, ns string) *SyncController {
	return &SyncController{
		argocdURL: url,
		token:     token,
		namespace: ns,
		interval:  30 * time.Second,
	}
}

func (c *SyncController) SyncApp(ctx context.Context, appName string) (*AppStatus, error) {
	// POST /api/v1/apps/{namespace}/{name}/sync
	url := fmt.Sprintf("%s/api/v1/apps/%s/%s/sync", c.argocdURL, c.namespace, appName)
	
	payload := map[string]interface{}{
		"revision": "HEAD",
	}
	body, _ := json.Marshal(payload)
	
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")
	
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	data, _ := io.ReadAll(resp.Body)
	var status AppStatus
	json.Unmarshal(data, &status)
	
	return &status, nil
}

func (c *SyncController) GetAppStatus(ctx context.Context, appName string) (*AppStatus, error) {
	url := fmt.Sprintf("%s/api/v1/apps/%s/%s", c.argocdURL, c.namespace, appName)
	
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	data, _ := io.ReadAll(resp.Body)
	var status AppStatus
	json.Unmarshal(data, &status)
	
	return &status, nil
}
```

### 自测题

<details>
<summary>Q1: Pipeline 的 Parallel 策略中，为什么用 errCh 收集错误而不是直接 return？</summary>

**答案**：

**原因**：并行执行时一个 goroutine 的 return 不影响其他 goroutine。用 channel 收集所有错误，等全部完成后统一处理。

```go
errCh := make(chan error, len(stage.Jobs))
// ... 每个 goroutine 发送错误到 errCh
wg.Wait()
close(errCh)
for err := range errCh {
    if err != nil { return err }
}
```

这样可以确保所有 job 都执行完再返回——即使某个 job 失败了，其他 job 的结果也会被记录。

</details>

<details>
<summary>Q2: 指数退避（Exponential Backoff）的公式是什么？为什么广告平台常用？</summary>

**答案**：

**公式**：`delay = base_delay × 2^attempt`

| 重试次数 | 延迟 |
|---------|------|
| 0 | 0s |
| 1 | 1s |
| 2 | 2s |
| 3 | 4s |
| 4 | 8s |

**广告平台场景**：Kafka 生产者发送失败、Redis 连接断开、DB 锁等待——这些瞬态故障用指数退避可以有效避免雪崩。

</details>

<details>
<summary>Q3: ArgoCD 的 Sync 和 Poll 模式有什么区别？生产环境推荐哪个？</summary>

**答案**：

| 模式 | 机制 | 延迟 | 适用场景 |
|------|------|------|---------|
| Poll | 定时拉取 Git 变更 | interval 级别 | 开发环境 |
| Webhook | Git push 触发 | 秒级 | **生产推荐** |

ArgoCD 默认每3分钟 poll 一次 Git。生产环境配置 GitHub/GitLab webhook，推送后秒级同步。

</details>
