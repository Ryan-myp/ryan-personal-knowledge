# 容器化与镜像优化深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、Docker 镜像优化

```
┌─────────────────────────────────────────────────────────────────────┐
│                     镜像优化策略                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  策略                    效果              实现难度                 │
│  ───────────────────────────────────────────────────────────    │
│  多阶段构建              -60% 体积          低                      │
│  精简基础镜像            -40% 体积          中                      │
│  合并 RUN 指令           -20% 层数          低                      │
│  使用 .dockerignore      -30% 构建时间      低                      │
│  缓存利用                -50% 构建时间      中                      │
│  镜像压缩                -15% 体积          低                      │
│                                                                     │
│  目标: 生产镜像 < 150MB, 构建时间 < 2分钟                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、多阶段构建

```dockerfile
# 文件: Dockerfile - Go 应用多阶段构建

# ─── 阶段 1: 编译 ───
FROM golang:1.22-alpine AS builder

WORKDIR /app

# 依赖缓存层 (利用 Docker 缓存)
COPY go.mod go.sum ./
RUN go mod download

# 复制源码
COPY . .

# 构建参数
ARG VERSION
ARG GIT_COMMIT
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-s -w -X main.version=${VERSION} -X main.commit=${GIT_COMMIT}" \
    -o /app/bin/server ./cmd/server

# ─── 阶段 2: 运行时 ───
FROM alpine:3.19 AS runtime

# 最小化运行时
RUN apk add --no-cache ca-certificates tzdata
ENV TZ=Asia/Shanghai

WORKDIR /app

# 仅复制二进制文件
COPY --from=builder /app/bin/server /app/server

# 非 root 用户运行
RUN adduser -D -u 1000 appuser
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/healthz || exit 1

CMD ["/app/server"]
```

---

## 三、容器运行时安全

```yaml
# 文件: k8s/pod-security.yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
  annotations:
    seccomp.security.alpha.kubernetes.io/pod: runtime/default
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  
  containers:
    - name: app
      image: ghcr.io/ryan-myp/ad-server:v1.2.3
      securityContext:
        allowPrivilegeEscalation: false
        privileged: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
          add:
            - NET_BIND_SERVICE
      
      volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: config
          mountPath: /etc/config
          readOnly: true
  
  volumes:
    - name: tmp
      emptyDir: {}
    - name: config
      configMap:
        name: app-config
```

---

## 四、镜像扫描与合规

```bash
# 文件: scripts/scan-image.sh

# Trivy 安全扫描
trivy image --severity HIGH,CRITICAL ghcr.io/ryan-myp/ad-server:v1.2.3

# 镜像大小分析
docker history ghcr.io/ryan-myp/ad-server:v1.2.3 --human

# 镜像合规检查
cosign verify \
  --certificate-identity-regexp=".*@ryan-myp.github.com" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/ryan-myp/ad-server:v1.2.3
```

---

## 五、参考资料

```
核心工具:
├── Docker Buildx
├── Kaniko (无守护进程构建)
├── Trivy (漏洞扫描)
└── Cosign (镜像签名)

最佳实践:
├── "Container Security" (Derek Morgan)
└── Kubernetes Hardening Guide
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
