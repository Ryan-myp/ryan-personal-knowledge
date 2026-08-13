# 容器安全加固 - 资深专家深度实现

## 一、安全层次

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    容器安全层次                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   层级                | 安全措施                                  │
│   ────────────────────┼──────────────────────────────────────────────│
│   镜像层             | 镜像扫描、基础镜像加固                  │
│   构建层             | 安全构建、多阶段构建                      │
│   运行层             | 运行时保护、权限控制                      │
│   网络层             | 网络策略、服务网格                        │
│   主机层             | 内核保护、补丁管理                        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、镜像安全实现

```go
package container_security

import (
    "context"
)

// ImageScanner 镜像扫描器
type ImageScanner struct {
    scanner *TrivyScanner
    policy  *PolicyEngine
}

// ScanResult 扫描结果
type ScanResult struct {
    Image      string
    Vulnerabilities []Vulnerability
    PolicyViolations []Violation
}

type Vulnerability struct {
    ID          string
    Severity    string
    Package     string
    Version     string
    Description string
}

type Violation struct {
    Rule    string
    Message string
}

// ScanImage 扫描镜像
func (s *ImageScanner) ScanImage(ctx context.Context, image string) (*ScanResult, error) {
    // 漏洞扫描
    vulns, err := s.scanner.Scan(ctx, image)
    if err != nil {
        return nil, err
    }
    
    // 策略检查
    violations, err := s.policy.Check(ctx, image)
    if err != nil {
        return nil, err
    }
    
    return &ScanResult{
        Image:             image,
        Vulnerabilities:  vulns,
        PolicyViolations: violations,
    }, nil
}
```

## 三、运行时保护实现

```go
package container_security

// RuntimeGuard 运行时保护
type RuntimeGuard struct {
    seccomp   *SeccompProfile
    apparmor  *AppArmorProfile
    capabilities []string
}

// SeccompProfile 系统调用过滤
type SeccompProfile struct {
    DefaultAction Scaction
    Syscalls      []SyscallRule
}

type Scaction string

const (
    ScAllow   Scaction = "SC_ACT_ALLOW"
    ScErrno   Scaction = "SC_ACT_ERRNO"
    ScKill    Scaction = "SC_ACT_KILL"
)

type SyscallRule struct {
    Names  []string
    Action Scaction
}

// ApplySecurityContext 应用安全上下文
func (g *RuntimeGuard) ApplySecurityContext() *corev1.SecurityContext {
    return &corev1.SecurityContext{
        RunAsNonRoot:   boolPtr(true),
        ReadOnlyRootfs: boolPtr(true),
        AllowPrivilegeEscalation: boolPtr(false),
        Capabilities: &corev1.Capabilities{
            Drop: []corev1.Capability{"ALL"},
        },
        SeccompProfile: &corev1.SeccompProfile{
            Type: corev1.SeccompProfileTypeLocalhost,
            LocalhostProfile: ptrPtr("profiles/restricted.json"),
        },
    }
}
```

## 四、面试高频题

### Q1: 容器安全的关键点？

```
A:
1. 镜像安全
2. 运行时保护
3. 权限控制
```

### Q2: 如何实现最小权限？

```
A:
1. 非root运行
2. 只读文件系统
3. 删除capabilities
```

## 五、自测题

1. 解释容器安全层次
2. 如何实现镜像扫描？
3. 如何配置运行时保护？

---

## 参考文档

- [Kubernetes Security](https://kubernetes.io/docs/concepts/security/)
- [Trivy](https://github.com/aquasecurity/trivy)
