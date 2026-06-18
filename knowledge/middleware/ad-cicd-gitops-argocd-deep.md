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
